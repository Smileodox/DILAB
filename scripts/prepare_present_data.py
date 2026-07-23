"""Data prep for the in-dashboard presentation mode (/present).

Produces three things, all deterministic and offline:
  1. ``cz`` (PC3) on every point in landscape_state_combi.json — enables the 3D
     result-space view. PC1/PC2 (cx/cy) stay untouched.
  2. Per-point cluster labels for the four structure lenses (one-hot/ordinal ×
     kmeans/HDBSCAN) into landscape_state_combi.structure.lens_labels — enables the
     "same field, four lenses" morph. Same parameters as structure.analyze_multi,
     so the silhouettes match the published ones.
  3. data/outputs/engine_validation_fields.json — 2D PCA point clouds of the two
     synthetic control fields (coupled S=3 / uncoupled S=0) from the engine-soundness
     validation, so the "metal detector" test can be SHOWN, not just quoted.

Run:  uv run python scripts/prepare_present_data.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import structure  # noqa: E402
from src.pipeline.clustering import cluster_and_select, config_matrix, hdbscan_cluster  # noqa: E402
from src.pipeline.combinatorial import sample_combinations  # noqa: E402
from src.pipeline.projection import _manifestation_index  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "outputs")


def _p(name):
    return os.path.join(OUT, name)


def _pca_coords(x: np.ndarray, k: int, sign_target: np.ndarray | None = None):
    """Top-k PCA coords of the centred matrix, with the same sign stabilisation as
    projection.project_config (orient each axis toward the pessimistic loadings)."""
    xc = x - x.mean(axis=0, keepdims=True)
    _, sv, vt = np.linalg.svd(xc, full_matrices=False)
    k = min(k, vt.shape[0])
    comps = vt[:k].copy()
    if sign_target is not None:
        for j in range(k):
            if float(comps[j] @ sign_target) < 0:
                comps[j] = -comps[j]
    coords = xc @ comps.T
    shares = (sv**2 / max(float((sv**2).sum()), 1e-12))[:k]
    return coords, [float(s) for s in shares]


def add_pc3_and_lens_labels():
    scenarios = json.load(open(_p("scenario_state_combi.json")))["scenarios"]
    morph = json.load(open(_p("morphbox_state.json")))
    ids = [s["id"] for s in scenarios]

    vocab = [m["id"] for m in morph["all_manifestations"]]
    x_oh = config_matrix(scenarios, vocab).astype(float)
    x_or = structure._ordinal_matrix_from_scenarios(scenarios, morph)

    # --- PC3 (same geometry + sign convention as the existing cx/cy projection) ---
    _, _, pos_by_manif, _ = _manifestation_index(morph)
    target = np.array([pos_by_manif.get(mid, 0.5) for mid in vocab]) - 0.5
    coords3, shares3 = _pca_coords(x_oh, 3, sign_target=target)
    cz_by_id = {sid: round(float(coords3[i, 2]), 4) for i, sid in enumerate(ids)}

    # --- Four lenses WITH per-point labels (params mirror structure.analyze_multi) ---
    km_oh = cluster_and_select(x_oh, ids, k=None, k_range=(2, 10), seed=42)
    km_or = cluster_and_select(x_or, ids, k=None, k_range=(2, 10), seed=42)
    hd_oh_labels, hd_oh_sil = hdbscan_cluster(x_oh, min_cluster_size=5, seed=42)
    hd_or_labels, hd_or_sil = hdbscan_cluster(x_or, min_cluster_size=5, seed=42)

    lens_labels = {
        "ids": ids,
        "onehot_kmeans": [int(v) for v in km_oh["labels"]],
        "ordinal_kmeans": [int(v) for v in km_or["labels"]],
        "onehot_hdbscan": [int(v) for v in hd_oh_labels],
        "ordinal_hdbscan": [int(v) for v in hd_or_labels],
    }
    sil_check = {
        "onehot_kmeans": round(float(km_oh["silhouette"]), 4),
        "ordinal_kmeans": round(float(km_or["silhouette"]), 4),
        "onehot_hdbscan": round(float(hd_oh_sil), 4),
        "ordinal_hdbscan": round(float(hd_or_sil), 4),
    }

    lp = _p("landscape_state_combi.json")
    land = json.load(open(lp))
    n_cz = 0
    for pt in land.get("points", []):
        cz = cz_by_id.get(pt["scenario_id"])
        if cz is not None:
            pt["cz"] = cz
            n_cz += 1
    land.setdefault("structure", {})["lens_labels"] = lens_labels
    land["structure"]["pc_shares_3d"] = [round(s, 4) for s in shares3]
    with open(lp, "w") as f:
        json.dump(land, f, indent=2)

    print(f"PC3: {n_cz}/{len(land['points'])} points | 3D variance shares: "
          f"{[round(s, 3) for s in shares3]}")
    print("lens silhouettes (recomputed vs published 0.074/0.17/0.3365/0.3799):")
    for k, v in sil_check.items():
        pub = land["structure"].get("lenses", {}).get(k, {}).get("silhouette")
        print(f"  {k}: {v} (published {pub})")


def dump_validation_fields():
    """2D point clouds of the synthetic control fields (mirrors validate_engine_soundness)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ves", os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_engine_soundness.py"))
    ves = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ves)

    fields = {}
    for key, strength in (("coupled", 3), ("uncoupled", 0)):
        box, mdict, didx, block = ves._synthetic_field()
        cib = ves._cib_matrix(block, box.drivers, strength)
        kept = sample_combinations(box, cib, didx, n_samples=150, oversample_factor=20,
                                   reject_threshold=0.35, seed=42)
        scenarios = structure.configs_to_scenarios([r.model_dump(mode="json") for r in kept])
        vocab = [m["id"] for m in mdict["all_manifestations"]]
        x = config_matrix(scenarios, vocab).astype(float)
        coords, shares = _pca_coords(x, 2)
        # Side label for colouring the coupled clusters: majority position of block-0
        # drivers. Synthetic manifestation ids encode driver + pole as "<driver>_o|_p".
        block0 = {d for d in box.drivers if block[d] == 0}
        sides = []
        for s in scenarios:
            chosen = [a["manifestation_id"] for a in s.get("assumptions", [])]
            pess = sum(1 for m in chosen
                       if m.rsplit("_", 1)[0] in block0 and m.endswith("_p"))
            sides.append(1 if pess > len(block0) / 2 else 0)
        fields[key] = {
            "x": [round(float(v), 4) for v in coords[:, 0]],
            "y": [round(float(v), 4) for v in coords[:, 1]],
            "side": sides,
            "n": len(scenarios),
            "pc_shares": [round(s, 4) for s in shares],
        }
        print(f"{key}: {len(scenarios)} configs, pc shares {[round(s,3) for s in shares]}")

    stats = json.load(open(_p("engine_validation.json")))
    with open(_p("engine_validation_fields.json"), "w") as f:
        json.dump({"fields": fields, "stats": stats}, f, indent=2)
    print("saved -> engine_validation_fields.json")


if __name__ == "__main__":
    add_pc3_and_lens_labels()
    dump_validation_fields()
