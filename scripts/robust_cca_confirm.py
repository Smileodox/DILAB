"""Cross-elicitation invariance test: does the central-raw <-> edge-distributed axis survive
when we STRIP the contrastive elicitation's inflated hard pairs? Offline, no LLM, no p-hacking.

Robust criterion (a priori, fixed — NOT chosen to preserve the axis): a hard(-2) incompatibility
is trusted only if BOTH the absolute AND the contrastive CCA flagged it. Contrastive-only hard
pairs (the ~half we judged fabricated) are zeroed. We then rebuild the field from three matrices
— robust-intersection, absolute-alone, and contrastive (baseline) — each with a threshold
calibrated to ITS OWN contradiction distribution (38th pctile, combi-parity), and let the
null-model test referee. If the axis survives on robust + absolute, the continuum is real; if it
collapses, the contrastive 'structure' was mostly inflation.
"""
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import functional, structure

D = "data/outputs/"


def _load(n):
    return json.load(open(D + n))


raw = _load("morphbox_zwicky_state.json")
morph = MorphologicalBox(
    drivers=raw["drivers"], manifestations=raw["manifestations"],
    all_manifestations=[DriverManifestation(**m) for m in raw["all_manifestations"]],
)
absolute = _load("cca_state.json")["cca"]
contrastive = _load("cca_state_contrastive.json")["cca"]


def hard_set(cca):
    s = set()
    for a, row in cca.items():
        for b, v in row.items():
            if v <= -2:
                s.add(frozenset((a, b)))
    return s


abs_hard, con_hard = hard_set(absolute), hard_set(contrastive)
robust_hard = abs_hard & con_hard
print(f"hard(-2) pairs: absolute={len(abs_hard)}  contrastive={len(con_hard)}  "
      f"robust(intersection)={len(robust_hard)}  contrastive-only(zeroed)={len(con_hard - abs_hard)}\n")

# Robust matrix = contrastive, with contrastive-only hard pairs neutralized to 0.
robust = {a: dict(row) for a, row in contrastive.items()}
for a, row in list(robust.items()):
    for b, v in list(row.items()):
        if v <= -2 and frozenset((a, b)) not in abs_hard:
            robust[a][b] = 0


def calibrated_threshold(cca, seed=42, n=8000, keep_pctile=38):
    rng = random.Random(seed)
    nonhard = []
    for _ in range(n):
        cfg = {d: rng.choice(morph.manifestations[d]) for d in morph.drivers}
        ratio, hard, _ = functional.cca_contradiction(cfg, morph, cca)
        if not hard:
            nonhard.append(ratio)
    return round(float(np.percentile(nonhard, keep_pctile)), 4) if nonhard else 0.25, len(nonhard), n


def run(label, cca):
    thr, survivors, n = calibrated_threshold(cca)
    configs = functional.sample_consistent(morph, cca, 120, oversample_factor=120.0,
                                           reject_threshold=thr, seed=42)
    hpairs = len(hard_set(cca))
    if len(configs) < 8:
        print(f"[{label}] hard={hpairs} thr={thr} hard-survivors={survivors}/{n} | only {len(configs)} kept — too few\n")
        return
    scens = structure.configs_to_scenarios([c.model_dump(mode="json") for c in configs])
    res = structure.analyze(scens, raw, null_trials=30, seed=42)
    o, z = res["observed"], res["z_scores"]
    print(f"[{label}] hard_pairs={hpairs} calibrated_thr={thr} hard-survivors={survivors}/{n} kept={len(configs)}")
    print(f"    silhouette={o['best_silhouette']} (z={z['best_silhouette']}) | "
          f"eff_dim={o['effective_dim']} (z={z['effective_dim']}) | pc1={o['pc1']} (z={z['pc1']})")
    print(f"    -> VERDICT: {res['verdict']}\n")


run("CONTRASTIVE (baseline, inflated)", contrastive)
run("ROBUST (absolute AND contrastive)", robust)
run("ABSOLUTE (alone, all-genuine)", absolute)
