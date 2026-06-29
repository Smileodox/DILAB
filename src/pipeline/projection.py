"""Linear, interpretable projection of the scenario config field — for navigation.

The landscape UMAP draws a meaningless blob on this field: by the null test in
``structure.py`` the kept sample is geometrically close to uniform random — a weak
continuum, not clusters — and UMAP's nonlinear axes carry no readable meaning and jump on
every reseed. This module replaces it with a PCA on the *same* one-hot config geometry, so
the two plotted axes ARE the dominant directions of variation and can be labelled by which
drivers load on them. It also emits a parallel-coordinates spec (one axis per driver) so
the recipe of each scenario is directly navigable, and reuses ``structure.analyze`` for an
honest clusters-vs-null verdict to show alongside the map.

Pure / numpy-only and offline (no LLM, no embeddings): consumes already-generated
scenarios + the parsed morphbox, so it is unit-testable and reproducible.
"""
from __future__ import annotations

import logging

import numpy as np

from src.pipeline import structure
from src.pipeline.clustering import config_matrix

log = logging.getLogger(__name__)

# How many strongest-loading drivers name an axis (kept short so the axis title is readable).
_TOP_DRIVERS_PER_AXIS = 3


def _manifestation_index(morphbox: dict):
    """Build lookups over the morphbox.

    Returns ``(label_by_id, driver_by_manif, pos_by_manif, order_by_driver)`` where
    ``pos_by_manif`` is the manifestation's normalised position in its driver's ordered
    list (0 = most optimistic … 1 = most pessimistic), the same convention as
    ``morphological._manif_position`` / ``infer_scenario_type``.
    """
    label_by_id, driver_by_manif = {}, {}
    for m in morphbox["all_manifestations"]:
        label_by_id[m["id"]] = m.get("label", m["id"])
        driver_by_manif[m["id"]] = m["driver_id"]
    pos_by_manif, order_by_driver = {}, {}
    for d in morphbox["drivers"]:
        order = morphbox["manifestations"].get(d, [])
        order_by_driver[d] = order
        n = len(order)
        for i, mid in enumerate(order):
            pos_by_manif[mid] = (i / (n - 1)) if n > 1 else 0.5
    return label_by_id, driver_by_manif, pos_by_manif, order_by_driver


def _axis_drivers(component, vocab, driver_by_manif, pos_by_manif, name_of):
    """Aggregate a PC's per-column loadings to driver level + a pessimistic/optimistic pole.

    ``weight`` = sum of |loading| over the driver's manifestation columns (how much the
    axis is "about" this driver). ``pole`` = which end the driver's pessimistic states sit
    on: sign of sum(loading * position); position 1 = pessimistic, so >= 0 means moving in
    the +axis direction pushes this driver toward 'pessimistisch'. Sign is stabilised by
    the caller so the labels are reproducible across runs.
    """
    weight, signed = {}, {}
    for col, mid in enumerate(vocab):
        d = driver_by_manif.get(mid)
        if d is None:
            continue
        load = float(component[col])
        weight[d] = weight.get(d, 0.0) + abs(load)
        signed[d] = signed.get(d, 0.0) + load * pos_by_manif.get(mid, 0.5)
    drivers = []
    for d, w in sorted(weight.items(), key=lambda kv: -kv[1]):
        pole = "pessimistic" if signed.get(d, 0.0) >= 0 else "optimistic"
        drivers.append({"driver_id": d, "name": name_of(d), "weight": round(w, 4), "pole": pole})
    return drivers


def _axis_label(key: str, share: float, drivers: list[dict]) -> str:
    """Human axis title, e.g. 'PC1 (23% var.): + A, C pessimistic · B optimistic'."""
    top = drivers[:_TOP_DRIVERS_PER_AXIS]
    if not top:
        return f"{key} ({share:.0%} var.)"
    pess = [d["name"] for d in top if d["pole"] == "pessimistic"]
    opti = [d["name"] for d in top if d["pole"] == "optimistic"]
    seg = []
    if pess:
        seg.append("+ " + ", ".join(pess) + " pessimistic")
    if opti:
        seg.append("+ " + ", ".join(opti) + " optimistic")
    return f"{key} ({share:.0%} var.): " + " · ".join(seg)


def project_config(scenarios, morphbox: dict, driver_names: dict | None = None,
                   k_range=(4, 10), null_trials: int = 20, seed: int = 42) -> dict:
    """PCA projection of the config field + interpretable axes + structure verdict + parcoords.

    Returns ``{coords, axes, structure, parcoords}``:
      - ``coords``    scenario_id -> [x, y] on the top-2 principal components.
      - ``axes``      ``pc1``/``pc2`` each with ``label``, ``share`` (variance fraction),
                      and driver loadings (``[{driver_id, name, weight, pole}]``).
      - ``structure`` observed-vs-null verdict from ``structure.analyze`` (effective_dim,
                      pc1_share, best_silhouette, null stats, ``has_usable_clusters``).
      - ``parcoords`` ``drivers`` (one axis per driver, ordered manifestation labels) +
                      ``rows`` (one per scenario: manifestation index per driver + pc1).
    """
    driver_names = driver_names or {}

    def name_of(d):
        return driver_names.get(d, d)

    vocab = [m["id"] for m in morphbox["all_manifestations"]]
    ids = [s.get("id", f"s{i}") for i, s in enumerate(scenarios)]
    x = config_matrix(scenarios, vocab).astype(float)  # (n, d) one-hot
    n, dim = x.shape

    label_by_id, driver_by_manif, pos_by_manif, order_by_driver = _manifestation_index(morphbox)

    # --- PCA on the centred config matrix -------------------------------------------
    comps = np.zeros((2, dim))
    coords = np.zeros((n, 2))
    axis_share = [0.0, 0.0]
    if n >= 2 and dim >= 1:
        xc = x - x.mean(axis=0, keepdims=True)
        _, sv, vt = np.linalg.svd(xc, full_matrices=False)  # vt: (min(n,dim), dim)
        var = sv ** 2
        total = float(var.sum()) or 1.0
        shares = var / total
        k = min(2, vt.shape[0])
        comps[:k] = vt[:k]
        coords = xc @ comps.T
        axis_share = [float(shares[i]) if i < shares.size else 0.0 for i in range(2)]
        # Sign stabilisation: orient each +axis toward 'pessimistic' loadings (column
        # positions) so labels/colors are reproducible despite SVD's sign ambiguity.
        target = np.array([pos_by_manif.get(mid, 0.5) for mid in vocab]) - 0.5
        for j in range(2):
            if float(comps[j] @ target) < 0:
                comps[j] = -comps[j]
                coords[:, j] = -coords[:, j]

    coords_by_id = {sid: [round(float(coords[i, 0]), 4), round(float(coords[i, 1]), 4)]
                    for i, sid in enumerate(ids)}

    axes = {}
    for j, key in enumerate(("pc1", "pc2")):
        drivers = _axis_drivers(comps[j], vocab, driver_by_manif, pos_by_manif, name_of)
        axes[key] = {
            "label": _axis_label(key.upper(), axis_share[j], drivers),
            "share": round(axis_share[j], 4),
            "drivers": drivers[: _TOP_DRIVERS_PER_AXIS * 2],  # cap payload, keep the strongest
        }

    # --- honest structure verdict (reuse the null-model machinery) -------------------
    verdict = structure.analyze(scenarios, morphbox, k_range=k_range,
                                null_trials=null_trials, seed=seed)
    obs, null = verdict["observed"], verdict["null"]
    struct = {
        "effective_dim": obs["effective_dim"],
        "pc1_share": obs["pc1"],
        "best_silhouette": obs["best_silhouette"],
        "best_k": obs.get("best_k"),
        "null": {
            "silhouette_mean": null["best_silhouette"]["mean"],
            "silhouette_std": null["best_silhouette"]["std"],
            "pc1_mean": null["pc1"]["mean"],
        },
        "has_usable_clusters": verdict["usable_structure"],
        "above_null": verdict["above_null"],
        "verdict": verdict["verdict"],
    }

    # --- parallel-coordinates spec (the recipe of each scenario) ---------------------
    pos_in_driver = {}  # manifestation_id -> index within its driver's ordered list
    for d in morphbox["drivers"]:
        for i, mid in enumerate(order_by_driver.get(d, [])):
            pos_in_driver[mid] = i

    pc_drivers = [
        {"driver_id": d, "name": name_of(d),
         "manifestations": [label_by_id.get(mid, mid) for mid in order_by_driver.get(d, [])]}
        for d in morphbox["drivers"]
    ]

    rows = []
    for i, s in enumerate(scenarios):
        manif_by_driver = {}
        for a in s.get("assumptions", []):
            mid = a.get("manifestation_id")
            d = driver_by_manif.get(mid)
            if d is not None:
                manif_by_driver[d] = mid
        values = [pos_in_driver.get(manif_by_driver.get(d), -1) for d in morphbox["drivers"]]
        rows.append({
            "scenario_id": ids[i],
            "type": s.get("type", "evolutionary"),
            "pc1": coords_by_id[ids[i]][0],
            "values": values,
        })

    return {
        "coords": coords_by_id,
        "axes": axes,
        "structure": struct,
        "parcoords": {"drivers": pc_drivers, "rows": rows},
    }
