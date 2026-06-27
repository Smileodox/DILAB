"""Null-model structure test for the scenario field.

Asks whether the generated scenarios carry any geometric structure that a uniform-random
sample of the same morphological field would not. If the observed statistics sit inside
the null distribution, the soft consistency filter (CIB / CCA) added no structure and no
clustering lever can recover archetypes — the honest, quantitative version of the
"no clusters emerge" finding.

Usage:
  uv run python analyze_structure.py                  # both methods, 20 null trials
  uv run python analyze_structure.py --trials 50      # tighter null distribution
"""
from __future__ import annotations

import argparse
import json
import logging
import os

from src.pipeline.structure import analyze

DATA = "data/outputs"

# method -> (scenario_state file, morphbox file)
METHODS = {
    "zwicky": ("scenario_state_zwicky.json", "morphbox_zwicky_state.json"),
    "combinatorial": ("scenario_state_combi.json", "morphbox_state.json"),
}


def _load(name: str):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def run(trials: int = 20, k_min: int = 4, k_max: int = 10, seed: int = 42) -> dict:
    report = {}
    for method, (scen_file, morph_file) in METHODS.items():
        scen_path = os.path.join(DATA, scen_file)
        morph_path = os.path.join(DATA, morph_file)
        if not (os.path.exists(scen_path) and os.path.exists(morph_path)):
            print(f"[skip] {method}: missing {scen_file} or {morph_file}")
            continue

        scenarios = _load(scen_file)["scenarios"]
        morphbox = _load(morph_file)
        res = analyze(scenarios, morphbox, k_range=(k_min, k_max), null_trials=trials, seed=seed)
        report[method] = res

        o, n, z = res["observed"], res["null"], res["z_scores"]
        verdict = res["verdict"]
        print(f"\n=== {method}  ({o['n']} scenarios, {o['dims']} manifestations) ===")
        print(f"  {'statistic':16} {'observed':>10} {'null mean±std':>18} {'z':>7}")
        print(f"  {'effective dim':16} {o['effective_dim']:>10} "
              f"{n['effective_dim']['mean']:>10}±{n['effective_dim']['std']:<6} {z['effective_dim']:>7}")
        print(f"  {'PC1 share':16} {o['pc1']:>10} "
              f"{n['pc1']['mean']:>10}±{n['pc1']['std']:<6} {z['pc1']:>7}")
        print(f"  {'best silhouette':16} {o['best_silhouette']:>10} "
              f"{n['best_silhouette']['mean']:>10}±{n['best_silhouette']['std']:<6} {z['best_silhouette']:>7}")
        print(f"  → verdict: {verdict}  (null = {n['trials']} uniform-random fields)")

    out_path = os.path.join(DATA, "structure_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport → {out_path}")
    return report


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    ap = argparse.ArgumentParser(description="Null-model structure test for the scenario field")
    ap.add_argument("--trials", type=int, default=20, help="number of uniform-random null fields")
    ap.add_argument("--k-min", type=int, default=4)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    run(trials=args.trials, k_min=args.k_min, k_max=args.k_max, seed=args.seed)


if __name__ == "__main__":
    main()
