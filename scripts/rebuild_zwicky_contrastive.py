"""Rebuild the Zwicky field from the CONTRASTIVE CCA matrix with a DISTRIBUTION-calibrated
consistency threshold, then let the null-model test referee. Offline (no LLM).

Named artifact being removed: the consistency filter was inert / un-calibrated (reject_threshold
0.25 never bit on the ratio distribution; max kept-contradiction ~0.11), and the on-disk field was
an absolute-CCA run. So contrastive coupling applied by a BITING threshold has never been cleanly
measured. We calibrate the threshold to the contradiction DISTRIBUTION (mirroring combi's ~38%
keep-rate) — NOT to silhouette — run structure.analyze ONCE, and accept whatever falls out.
"""
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import functional, structure

DATA = "data/outputs"


def _load(n):
    return json.load(open(os.path.join(DATA, n)))


raw = _load("morphbox_zwicky_state.json")
morph = MorphologicalBox(
    drivers=raw["drivers"],
    manifestations=raw["manifestations"],
    all_manifestations=[DriverManifestation(**m) for m in raw["all_manifestations"]],
)
cca = _load("cca_state_contrastive.json")["cca"]
print(f"Contrastive CCA + Zwicky morphbox: {len(morph.drivers)} functions, "
      f"{len(morph.all_manifestations)} directions\n", flush=True)

# ── 1. Measure the contradiction distribution over uniform-random configs ──
rng = random.Random(42)
N = 8000
ratios, nonhard, n_hard = [], [], 0
for _ in range(N):
    cfg = {d: rng.choice(morph.manifestations[d]) for d in morph.drivers}
    ratio, hard, _net = functional.cca_contradiction(cfg, morph, cca)
    ratios.append(ratio)
    if hard:
        n_hard += 1
    else:
        nonhard.append(ratio)

pct = lambda arr, q: float(np.percentile(arr, q)) if arr else float("nan")
print(f"Random configs: {N} drawn | HARD(-2 present) {n_hard} ({100*n_hard/N:.1f}%) -> rejected by hard-gate")
print(f"  all-ratio percentiles:   p10={pct(ratios,10):.3f} p25={pct(ratios,25):.3f} "
      f"p50={pct(ratios,50):.3f} p75={pct(ratios,75):.3f} max={max(ratios):.3f}")
if nonhard:
    print(f"  non-hard ratio pctiles:  p10={pct(nonhard,10):.3f} p38={pct(nonhard,38):.3f} "
          f"p50={pct(nonhard,50):.3f} p75={pct(nonhard,75):.3f}")
print(f"  configs surviving hard-gate: {len(nonhard)} ({100*len(nonhard)/N:.1f}%)")
print(f"  of those, ratio<=0.25 (the OLD threshold): {sum(1 for r in nonhard if r<=0.25)} "
      f"({100*sum(1 for r in nonhard if r<=0.25)/max(1,len(nonhard)):.1f}%) -> shows 0.25 was inert\n")

# ── 2. A-priori calibration: keep the most-consistent ~38% of hard-free configs (combi parity).
#      Chosen to reject the contradictory tail, NOT tuned to silhouette.
thr_cal = round(pct(nonhard, 38), 4) if nonhard else 0.25
print(f"Calibrated threshold (38th pctile of non-hard ratios, combi-parity): {thr_cal}\n")

# ── 3. Sample + null-test at the OLD (0.25) and CALIBRATED thresholds. One shot each. ──
def run_at(label, thr):
    configs = functional.sample_consistent(morph, cca, 120, oversample_factor=80.0,
                                           reject_threshold=thr, seed=42)
    if len(configs) < 8:
        print(f"[{label}] thr={thr}: only {len(configs)} kept — too few for a structure test")
        return
    scens = structure.configs_to_scenarios([c.model_dump(mode="json") for c in configs])
    res = structure.analyze(scens, raw, null_trials=30, seed=42)
    o, z = res["observed"], res["z_scores"]
    kept_ratios = [c.contradiction_ratio for c in configs]
    print(f"[{label}] thr={thr} | kept {len(configs)} | kept-ratio max={max(kept_ratios):.3f} mean={np.mean(kept_ratios):.3f}")
    print(f"    silhouette={o['best_silhouette']} (z={z['best_silhouette']}) | "
          f"eff_dim={o['effective_dim']} (z={z['effective_dim']}) | pc1={o['pc1']} (z={z['pc1']})")
    print(f"    -> VERDICT: {res['verdict']}\n")


run_at("OLD 0.25", 0.25)
run_at("CALIBRATED", thr_cal)
