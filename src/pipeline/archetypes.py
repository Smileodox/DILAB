"""Archetype extraction — name the dense-core clusters of the combinatorial scenario field.

The field is a HYBRID: a dense archetypal core (a minority of configs form tight clusters) inside a
continuum halo (the majority). KMeans-on-all-points hides this — it forces the halo into spherical
clusters and reports a near-zero silhouette. This module instead uses ORDINAL encoding (keeping the
optimistic→pessimistic ordering of manifestations) + UMAP→HDBSCAN (density-based, permits a noise /
continuum halo) to isolate the core, then:
  - labels each cluster with an LLM (name + description) off its DISTINGUISHING drivers + example
    narratives (c-TF-IDF-style lift: states over-represented in the cluster vs the rest of the field);
  - marks which clusters contain a CIB fixed point (an "attractor", via morphological.is_fixed_point);
  - stays HONEST about the continuum (reports ``noise_fraction``; does not pretend the field clusters).

Domain-agnostic: no domain taxonomy is hardwired; identity comes from the drivers/narratives.
Deterministic (seeded). ``label_fn`` is injectable so the clustering is unit-testable offline.
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np

from src.config import SCENARIO_MODEL
from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import clustering, morphological
from src.prompts.archetypes import CLUSTER_LABEL

log = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 5   # HDBSCAN: smallest dense group that counts as an archetype
UMAP_COMPONENTS = 5    # reduce the ordinal config space before density clustering
TOP_DISTINGUISHING = 5  # distinguishing drivers reported/sent to the labeller per archetype


def _ordinal_matrix(configs: list[dict], box: MorphologicalBox) -> np.ndarray:
    """One ordinal value per driver: manifestation position 0 (optimistic) … 1 (pessimistic)."""
    x = np.zeros((len(configs), len(box.drivers)))
    for r, c in enumerate(configs):
        cfg = c.get("configuration", {})
        for j, d in enumerate(box.drivers):
            ms = box.manifestations.get(d, [])
            mid = cfg.get(d)
            if mid in ms:
                x[r, j] = ms.index(mid) / (len(ms) - 1) if len(ms) > 1 else 0.5
    return x


def _distinguishing(member_idx: list[int], configs: list[dict], box: MorphologicalBox,
                    driver_name: dict, label_by_manif: dict, driver_by_manif: dict) -> list[dict]:
    """States over-represented in this cluster vs the whole field (lift), mapped to readable names."""
    n_all = len(configs)
    # per-manifestation frequency in the cluster and overall
    def freq(idxs):
        counts: dict[str, int] = {}
        for i in idxs:
            for mid in configs[i].get("configuration", {}).values():
                counts[mid] = counts.get(mid, 0) + 1
        return {mid: c / max(1, len(idxs)) for mid, c in counts.items()}

    f_cluster = freq(member_idx)
    f_all = freq(list(range(n_all)))
    lifts = []
    for mid, fc in f_cluster.items():
        lift = fc - f_all.get(mid, 0.0)
        if lift > 0:
            d = driver_by_manif.get(mid, "")
            lifts.append({
                "driver": driver_name.get(d, d),
                "manifestation": label_by_manif.get(mid, mid),
                "lift": round(lift, 3),
            })
    lifts.sort(key=lambda z: -z["lift"])
    return lifts[:TOP_DISTINGUISHING]


def _label_via_llm(features: list[dict], narratives: list[str], domain: str, model: str) -> dict:
    """Name + describe an archetype from its distinguishing drivers + example narratives."""
    from src.llm import safe_chat_json

    feat_txt = "\n".join(f"- {f['driver']}: {f['manifestation']}" for f in features) or "- (none)"
    narr = ""
    if narratives:
        joined = "\n\n".join(n[:600] for n in narratives[:2])
        narr = f"\nExample scenario excerpts from this group:\n{joined}\n"
    result = safe_chat_json(
        CLUSTER_LABEL.format(domain=domain, features=feat_txt, narrative_block=narr),
        system="You name and contrast qualitative scenario archetypes. Be concise and specific.",
        model=model,
    )
    name = (result.get("name") or "").strip()
    desc = (result.get("description") or "").strip()
    return {"name": name, "description": desc}


def run(
    combinatorial_state_path: str = "data/outputs/combinatorial_state.json",
    morphbox_state_path: str = "data/outputs/morphbox_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    scenario_state_path: str = "data/outputs/scenario_state_combi.json",
    output_path: str = "data/outputs/archetypes_state.json",
    model: str | None = None,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    label_fn=None,
    seed: int = 42,
    profile=None,
) -> dict:
    """Cluster the combinatorial field into named archetypes + a continuum halo. Returns the state."""
    model = model or SCENARIO_MODEL
    label_fn = label_fn or _label_via_llm
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    domain = profile.prompt_kwargs().get("domain", "the domain")

    with open(combinatorial_state_path) as f:
        configs = json.load(f)["configs"]
    with open(morphbox_state_path) as f:
        mb = json.load(f)
    box = MorphologicalBox(drivers=mb["drivers"], manifestations=mb["manifestations"],
                           all_manifestations=[DriverManifestation(**m) for m in mb["all_manifestations"]])

    driver_name = {}
    try:
        with open(merge_state_path) as f:
            driver_name = {d["id"]: d.get("name", d["id"]) for d in json.load(f).get("unified_drivers", [])}
    except (FileNotFoundError, KeyError):
        pass
    label_by_manif = {m["id"]: m.get("label", m["id"]) for m in mb["all_manifestations"]}
    driver_by_manif = {m["id"]: m["driver_id"] for m in mb["all_manifestations"]}

    narrative_by_id = {}
    if os.path.exists(scenario_state_path):
        with open(scenario_state_path) as f:
            for s in json.load(f).get("scenarios", []):
                if s.get("narrative"):
                    narrative_by_id[s.get("id")] = s["narrative"]

    if len(configs) < min_cluster_size * 2:
        state = {"method": "hdbscan_ordinal", "n_configs": len(configs), "noise_fraction": 1.0,
                 "hdbscan_silhouette": None, "archetypes": [],
                 "continuum": {"n_noise": len(configs), "note": "too few configs to cluster"}}
        _write(state, output_path)
        return state

    x = _ordinal_matrix(configs, box)
    labels, sil = clustering.hdbscan_cluster(x, min_cluster_size=min_cluster_size,
                                             n_components=UMAP_COMPONENTS, seed=seed)

    # attractor overlay: which configs are strict CIB fixed points (deterministic, no LLM)
    with open(cib_state_path) as f:
        cib = json.load(f)
    cib_matrix, driver_index = cib["matrix"], {d: i for i, d in enumerate(cib["driver_ids"])}
    is_fp = [morphological.is_fixed_point(c.get("configuration", {}), box, cib_matrix, driver_index)
             for c in configs]

    archetypes = []
    cluster_ids = sorted(l for l in set(labels) if l != -1)
    for cl in cluster_ids:
        member_idx = [i for i, l in enumerate(labels) if l == cl]
        centroid = x[member_idx].mean(axis=0)
        rep_local = min(member_idx, key=lambda i: float(np.linalg.norm(x[i] - centroid)))
        rep_id = configs[rep_local].get("id", f"c{rep_local}")
        features = _distinguishing(member_idx, configs, box, driver_name, label_by_manif, driver_by_manif)
        narrs = [narrative_by_id[configs[i]["id"]] for i in member_idx
                 if configs[i].get("id") in narrative_by_id]
        labeled = label_fn(features, narrs, domain, model)
        archetypes.append({
            "id": f"archetype_{cl}",
            "label": labeled.get("name") or f"Archetype {cl}",
            "description": labeled.get("description", ""),
            "size": len(member_idx),
            "member_scenario_ids": [configs[i].get("id", f"c{i}") for i in member_idx],
            "distinguishing_drivers": features,
            "representative_scenario_id": rep_id,
            "contains_attractor": any(is_fp[i] for i in member_idx),
        })

    # Ordered label per config (index-aligned with combinatorial_state / scenarios / landscape points),
    # so the UI can colour the landscape scatter by archetype without an id join. "-1" → Continuum.
    label_by_cluster = {int(cl): a["label"] for cl, a in zip(cluster_ids, archetypes)}
    config_labels = [label_by_cluster.get(int(l), "Continuum") for l in labels]

    n_noise = int((labels == -1).sum())
    state = {
        "method": "hdbscan_ordinal",
        "n_configs": len(configs),
        "config_labels": config_labels,
        "min_cluster_size": min_cluster_size,
        "n_archetypes": len(archetypes),
        "noise_fraction": round(n_noise / len(configs), 3),
        "hdbscan_silhouette": sil,
        "n_fixed_points": int(sum(is_fp)),
        "archetypes": archetypes,
        "continuum": {
            "n_noise": n_noise,
            "note": (f"{n_noise}/{len(configs)} configs form no dense cluster — the continuum halo; "
                     "archetypes describe only the dense core, not the whole field."),
        },
    }
    _write(state, output_path)
    print(f"  Archetypes: {len(archetypes)} named clusters, {n_noise}/{len(configs)} continuum "
          f"(silhouette {sil})", flush=True)
    return state


def _write(state: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
