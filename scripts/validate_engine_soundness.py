"""Engine-soundness validation — is the flat spectrum silhouette the ENGINE or the CORPUS?

Runs three fields through the SAME structure test (src.pipeline.structure.analyze):
  1. POSITIVE control — synthetic block-antagonistic coupling (S=3): engine SHOULD find clusters.
  2. NEGATIVE control — zero coupling (S=0): inert filter → uniform-random → no structure.
  3. REAL 4-axis spectrum field — the live combinatorial output (scenario_state_combi.json).

If (1) separates cleanly and (2)/(3) do not, the flat spectrum silhouette is a driver-coupling /
corpus property, NOT an engine defect. This mirrors tests/test_capability.py (the coupled/uncoupled
controls) and adds the real field as a third arm.

NOTE on scope: our engine is a SIMPLIFIED, driver-level ordinal CIB (support_score in
morphological.py), not Weimer-Jehle's full state x state judgment matrix — so an external CIB
benchmark matrix cannot be fed 1:1. This synthetic positive control is the format-matched,
deterministic, offline equivalent of that gold-standard check.

Run:  uv run python scripts/validate_engine_soundness.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import structure
from src.pipeline.combinatorial import sample_combinations

N_DRIVERS = 8
BLOCK_SIZE = 4


def _synthetic_field():
    drivers = [f"d{i}" for i in range(N_DRIVERS)]
    manifs = {d: [f"{d}_o", f"{d}_p"] for d in drivers}  # index 0 = optimistic, 1 = pessimistic
    all_manifestations = [
        {"id": m, "driver_id": d, "label": m, "description": "", "plausibility": "medium"}
        for d in drivers for m in manifs[d]
    ]
    box = MorphologicalBox(
        drivers=drivers, manifestations=manifs,
        all_manifestations=[DriverManifestation(**m) for m in all_manifestations],
    )
    mdict = {"drivers": drivers, "manifestations": manifs, "all_manifestations": all_manifestations}
    driver_index = {d: i for i, d in enumerate(drivers)}
    block = {d: (0 if i < BLOCK_SIZE else 1) for i, d in enumerate(drivers)}
    return box, mdict, driver_index, block


def _cib_matrix(block, drivers, strength):
    n = len(drivers)
    m = [[0] * n for _ in range(n)]
    for a in range(n):
        for b in range(n):
            if a != b:
                m[a][b] = strength if block[drivers[a]] == block[drivers[b]] else -strength
    return m


def _run_synthetic(strength):
    box, mdict, didx, block = _synthetic_field()
    cib = _cib_matrix(block, box.drivers, strength)
    kept = sample_combinations(box, cib, didx, n_samples=150, oversample_factor=20,
                               reject_threshold=0.35, seed=42)
    scenarios = structure.configs_to_scenarios([r.model_dump(mode="json") for r in kept])
    return structure.analyze(scenarios, mdict, k_range=(2, 6), null_trials=20, seed=42), len(kept)


def _summarize(res):
    o, z = res.get("observed", {}), res.get("z_scores", {})
    def r(x, n=4):
        try: return round(float(x), n)
        except Exception: return None
    return {
        "verdict": res.get("verdict"),
        "usable_structure": res.get("usable_structure"),
        "best_silhouette": r(o.get("best_silhouette")),
        "pc1_share": r(o.get("pc1")),
        "effective_dim": r(o.get("effective_dim"), 2),
        "z_silhouette": r(z.get("best_silhouette"), 2),
    }


def main():
    out = {}
    res_on, n_on = _run_synthetic(3)
    out["positive_control_coupled"] = {"n_kept": n_on, **_summarize(res_on)}
    res_off, n_off = _run_synthetic(0)
    out["negative_control_uncoupled"] = {"n_kept": n_off, **_summarize(res_off)}

    scen = json.load(open("data/outputs/scenario_state_combi.json"))["scenarios"]
    morph = json.load(open("data/outputs/morphbox_state.json"))
    res_real = structure.analyze(scen, morph, k_range=(2, 8), null_trials=20, seed=42)
    out["real_spectrum_4axis"] = {"n_scenarios": len(scen), **_summarize(res_real)}

    print(json.dumps(out, indent=2))
    with open("data/outputs/engine_validation.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nSaved -> data/outputs/engine_validation.json")


if __name__ == "__main__":
    main()
