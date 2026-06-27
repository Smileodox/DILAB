"""Experiment: does forced-contrast CCA break the LLM positivity bias and give the
scenario field real structure?

Holds everything fixed except the CCA elicitation. Reuses the existing Zwicky morphbox
(no re-extraction), runs both the absolute and the contrastive CCA, re-samples consistent
configs from each, and scores both against the null-model structure test. The absolute CCA
field is statistically indistinguishable from a uniform-random sample of the field; this
asks whether the contrastive elicitation clears that bar.

  uv run python experiment_cca.py
  uv run python experiment_cca.py --n 120 --reject 0.25 --model gpt-5.4
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from collections import Counter

from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import functional, structure

DATA = "data/outputs"


def _p(name):
    return os.path.join(DATA, name)


def _load(name):
    with open(_p(name)) as f:
        return json.load(f)


def cca_stats(cca: dict) -> dict:
    seen, scores = set(), []
    for a, row in cca.items():
        for b, s in row.items():
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            scores.append(s)
    if not scores:
        return {"pairs": 0}
    return {
        "pairs": len(scores),
        "mean": round(sum(scores) / len(scores), 3),
        "neg": sum(1 for s in scores if s < 0),
        "hard": sum(1 for s in scores if s <= -2),
        "pos": sum(1 for s in scores if s > 0),
        "dist": dict(sorted(Counter(scores).items())),
    }


def _morphbox():
    raw = _load("morphbox_zwicky_state.json")
    morph = MorphologicalBox(
        drivers=raw["drivers"],
        manifestations=raw["manifestations"],
        all_manifestations=[DriverManifestation(**m) for m in raw["all_manifestations"]],
    )
    manif_by_id = {m.id: m for m in morph.all_manifestations}
    name_by_fid = {d["id"]: d["name"] for d in _load("functional_merge_state.json")["unified_drivers"]}
    return raw, morph, manif_by_id, name_by_fid


def evaluate(label: str, cca: dict, morph, raw, n: int, reject: float, seed: int) -> dict:
    cs = cca_stats(cca)
    print(f"\n### {label} CCA")
    print(f"  pairs={cs['pairs']} mean={cs.get('mean')} neg={cs.get('neg')} "
          f"hard(-2)={cs.get('hard')} pos={cs.get('pos')}  dist={cs.get('dist')}")
    configs = functional.sample_consistent(morph, cca, n, oversample_factor=80.0,
                                            reject_threshold=reject, seed=seed)
    if len(configs) < 8:
        print(f"  only {len(configs)} configs kept — too few for a structure test")
        return {"cca": cs, "n_configs": len(configs)}
    scens = structure.configs_to_scenarios([c.model_dump(mode="json") for c in configs])
    res = structure.analyze(scens, raw, null_trials=30, seed=seed)
    o, z = res["observed"], res["z_scores"]
    print(f"  kept {len(configs)} configs | silhouette={o['best_silhouette']} (z={z['best_silhouette']}) "
          f"effdim={o['effective_dim']} (z={z['effective_dim']}) pc1={o['pc1']} (z={z['pc1']})")
    print(f"  → VERDICT: {res['verdict']}")
    return {"cca": cs, "n_configs": len(configs), "structure": res}


def run(n: int = 120, reject: float = 0.25, model: str = "gpt-5.4", seed: int = 42,
        max_workers: int = 6) -> dict:
    raw, morph, manif_by_id, name_by_fid = _morphbox()
    print(f"Reusing Zwicky morphbox: {len(morph.drivers)} functions, "
          f"{len(morph.all_manifestations)} directions")

    # Baseline: cached absolute CCA if present, else compute it.
    if os.path.exists(_p("cca_state.json")):
        cca_abs = _load("cca_state.json")["cca"]
        print("Loaded cached absolute CCA (cca_state.json)")
    else:
        cca_abs = functional.assess_cca(morph, manif_by_id, name_by_fid, model, max_workers, mode="absolute")

    print("\nRunning contrastive CCA (forced-contrast elicitation) ...", flush=True)
    cca_con = functional.assess_cca(morph, manif_by_id, name_by_fid, model, max_workers, mode="contrastive")
    json.dump({"cca": cca_con, "n_functions": len(morph.drivers), "mode": "contrastive"},
              open(_p("cca_state_contrastive.json"), "w"), indent=2)

    out = {
        "absolute": evaluate("ABSOLUTE (baseline)", cca_abs, morph, raw, n, reject, seed),
        "contrastive": evaluate("CONTRASTIVE", cca_con, morph, raw, n, reject, seed),
    }
    json.dump(out, open(_p("experiment_cca_report.json"), "w"), indent=2, default=str)
    print(f"\nReport → {_p('experiment_cca_report.json')}")
    return out


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    ap = argparse.ArgumentParser(description="Absolute vs contrastive CCA, scored by the null-model structure test")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--reject", type=float, default=0.25, help="max contradiction_ratio to keep")
    ap.add_argument("--model", default="gpt-5.4")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-workers", type=int, default=6)
    args = ap.parse_args()
    run(n=args.n, reject=args.reject, model=args.model, seed=args.seed, max_workers=args.max_workers)


if __name__ == "__main__":
    main()
