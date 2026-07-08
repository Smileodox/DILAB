"""Combinatorial scenario pipeline (Soft-CIB sampling + embedding clustering).

Runs ALONGSIDE the baseline morphological/CIB notebooks. It reuses the same inputs
(morphbox_state.json + cib_state.json) and the same downstream code (scenario_gen,
landscape, evaluation), but replaces the hard Weimer-Jehle fixed-point gate with a soft
CIB consistency filter over a broad sample of the morphological field, and lets scenario
structure emerge bottom-up from narrative-embedding clusters instead of imposed archetypes.

All outputs carry a `_combi` suffix so both methods can be compared side by side:

    1. combinatorial.run        morphbox + cib              -> combinatorial_state.json
    2. scenario_gen.run(short)  combinatorial_state         -> scenario_state_combi.json
    3. embed + cluster          narratives                  -> labels + representatives
    4. landscape.run (+cluster) scenario_state_combi        -> landscape_state_combi.json
    5. representatives subset                                -> scenario_state_combi_representatives.json
    6. evaluation.run (reps)    representatives             -> final_analysis_combi.json

Usage:
    uv run python run_combinatorial.py                 # full run (needs Azure + Chroma KB)
    uv run python run_combinatorial.py --smoke         # N=8, k=3, no RAG, cheap end-to-end
    uv run python run_combinatorial.py --sample-only   # stage 1 only, no LLM at all
"""

from __future__ import annotations

import argparse
import json
import logging
import os

import numpy as np

from src import config
from src.pipeline import combinatorial, landscape, scenario_gen

log = logging.getLogger(__name__)
DATA_DIR = "data/outputs"


def _p(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def _try_get_collection():
    """Return the Chroma KB collection, or None if unavailable (e.g. KB not built)."""
    try:
        from src.rag import get_collection

        return get_collection()
    except Exception as e:  # noqa: BLE001 — best-effort; RAG grounding is optional
        log.warning("No Chroma collection available (%s) — continuing without RAG grounding.", e)
        return None


def run(
    n_samples: int | None = None,
    reject_threshold: float | None = None,
    n_clusters: int | None = None,
    seed: int | None = None,
    skip_rag: bool = False,
    skip_eval: bool = False,
    sample_only: bool = False,
    max_workers: int | None = None,
    narrative_mode: str = "short",
    model: str | None = None,
    landscape_space: str = "config",
    outdir: str = DATA_DIR,
) -> dict:
    n_clusters = config.COMBI_N_CLUSTERS if n_clusters is None else n_clusters
    # Default narratives to the pooled SCENARIO_MODEL (gpt-5.4, spread across all endpoints)
    # instead of scenario_gen's fallback chat deployment (gpt-4.1-mini, single endpoint → 429s).
    model = model or config.SCENARIO_MODEL

    combi_path = os.path.join(outdir, "combinatorial_state.json")
    scen_path = os.path.join(outdir, "scenario_state_combi.json")
    reps_path = os.path.join(outdir, "scenario_state_combi_representatives.json")
    landscape_path = os.path.join(outdir, "landscape_state_combi.json")
    final_path = os.path.join(outdir, "final_analysis_combi.json")

    # --- Stage 1: sample the morphological field, soft-CIB filter (no LLM) ----------
    print("\n[1/6] Sampling combinations with soft-CIB filter ...")
    combi_state = combinatorial.run(
        morphbox_state_path=_p("morphbox_state.json"),
        cib_state_path=_p("cib_state.json"),
        output_path=combi_path,
        n_samples=n_samples,
        reject_threshold=reject_threshold,
        seed=seed,
    )
    n_combos = combi_state["n_combinations"]
    if sample_only:
        print(f"  --sample-only: stopped after stage 1 ({n_combos} combinations).")
        return {"combinatorial_state": combi_path, "n_combinations": n_combos}
    if n_combos == 0:
        print("  No combinations kept — relax COMBI_REJECT_THRESHOLD. Aborting.")
        return {"combinatorial_state": combi_path, "n_combinations": 0}

    # --- Stage 2: short, grounded narratives for every kept combination -------------
    print(f"\n[2/6] Generating {n_combos} short narratives ...")
    collection = None if skip_rag else _try_get_collection()
    scenario_gen.run(
        consistency_state_path=combi_path,
        morphbox_state_path=_p("morphbox_state.json"),
        cib_state_path=_p("cib_state.json"),
        merge_state_path=_p("merge_state.json"),
        output_path=scen_path,
        narrative_mode=narrative_mode,
        max_workers=max_workers,
        collection=collection,
        model=model,
    )

    # --- Stage 3: build geometry + cluster ------------------------------------------
    # Default geometry is the CONFIG space (one-hot manifestation vectors): distances
    # reflect structural difference between scenarios. Narrative embeddings of same-domain
    # text collapse to ~0.9 cosine and hide that diversity, so they are opt-in only.
    from src.pipeline.clustering import cluster_and_select, config_matrix

    with open(scen_path) as f:
        scenarios = json.load(f)["scenarios"]
    ids = [s["id"] for s in scenarios]

    if landscape_space == "narrative":
        print("\n[3/6] Embedding narratives and clustering ...")
        from src.llm import embed
        geom = np.array(embed([s["narrative"][:8000] for s in scenarios]))
    else:
        print("\n[3/6] Building config-space geometry and clustering ...")
        with open(_p("morphbox_state.json")) as f:
            vocab = [m["id"] for m in json.load(f)["all_manifestations"]]
        geom = config_matrix(scenarios, vocab)

    clustering = cluster_and_select(
        geom, ids,
        k=(n_clusters if n_clusters and n_clusters > 0 else None),
        k_range=config.COMBI_CLUSTER_K_RANGE,
        seed=config.COMBI_SEED,
    )
    cluster_by_id = dict(zip(ids, clustering["labels"]))
    rep_ids = set(clustering["representative_ids"])
    print(f"  space={landscape_space}, k={clustering['k']}, silhouette={clustering['silhouette']}, "
          f"{len(rep_ids)} representatives of {n_combos}")

    # --- Stage 4: landscape over ALL combos, annotated with cluster membership ------
    print("\n[4/6] Building UMAP landscape ...")
    landscape_state = landscape.run(
        scenario_state_path=scen_path,
        output_path=landscape_path,
        consistency_state_path=combi_path,
        embeddings=geom,
    )
    for pt in landscape_state.get("points", []):
        sid = pt["scenario_id"]
        pt["cluster"] = int(cluster_by_id.get(sid, -1))
        pt["is_representative"] = sid in rep_ids
    landscape_state.setdefault("metadata", {}).update({
        "method": "combinatorial",
        "geometry": landscape_space,
        "n_clusters": clustering["k"],
        "silhouette": clustering["silhouette"],
    })

    # Interpretable PCA projection + parallel-coords + honest structure verdict (replaces
    # the meaningless UMAP axes for navigation; UMAP x,y stay as a baseline).
    try:
        from src.pipeline import projection
        with open(_p("morphbox_state.json")) as f:
            morph = json.load(f)
        try:
            with open(_p("merge_state.json")) as f:
                merge = json.load(f)
            dnames = {d["id"]: d.get("name", d["id"]) for d in merge.get("unified_drivers", [])}
        except Exception:  # noqa: BLE001
            dnames = None
        proj = projection.project_config(scenarios, morph, driver_names=dnames, seed=seed)
        for pt in landscape_state.get("points", []):
            xy = proj["coords"].get(pt["scenario_id"])
            if xy:
                pt["cx"], pt["cy"] = xy
        landscape_state["axes"] = proj["axes"]
        landscape_state["structure"] = proj["structure"]
        landscape_state["parcoords"] = proj["parcoords"]
        print(f"  projection: {proj['structure']['verdict']} "
              f"(PC1 {proj['axes']['pc1']['share']:.0%}, silhouette {proj['structure']['best_silhouette']})")
    except Exception as e:  # noqa: BLE001
        print(f"  projection failed ({e}); landscape written without PCA axes.")

    with open(landscape_path, "w") as f:
        json.dump(landscape_state, f, indent=2)

    # --- Stage 5: representatives subset (the headline scenarios for MCDA) -----------
    print("\n[5/6] Writing representatives subset ...")
    reps = [s for s in scenarios if s["id"] in rep_ids]
    with open(reps_path, "w") as f:
        json.dump({"scenarios": reps}, f, indent=2)
    print(f"  {len(reps)} representative scenarios → {reps_path}")

    # --- Stage 6: MCDA on representatives only (cost cap) ----------------------------
    if skip_eval:
        print("\n[6/6] --skip-eval: MCDA skipped.")
    elif collection is None and skip_rag:
        print("\n[6/6] MCDA skipped (no RAG collection in --skip-rag mode).")
    else:
        print(f"\n[6/6] Running MCDA on {len(reps)} representatives ...")
        try:
            from src.pipeline import evaluation

            evaluation.run(
                scenario_state_path=reps_path,
                merge_state_path=_p("merge_state.json"),
                kb_state_path=_p("kb_state.json"),
                cib_state_path=_p("cib_state.json"),
                output_path=final_path,
            )
        except Exception as e:  # noqa: BLE001
            print(f"  MCDA stage failed ({e}). The other *_combi.json outputs are still written.")

    print("\nDone. Outputs:")
    for path in (combi_path, scen_path, reps_path, landscape_path, final_path):
        print(f"  {'✓' if os.path.exists(path) else '·'} {path}")
    return {
        "combinatorial_state": combi_path,
        "scenario_state": scen_path,
        "representatives": reps_path,
        "landscape": landscape_path,
        "final_analysis": final_path,
        "n_combinations": n_combos,
        "n_clusters": clustering["k"],
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Combinatorial scenario pipeline (Soft-CIB + clustering)")
    ap.add_argument("--n-samples", type=int, default=None, help="target kept combinations (default config.COMBI_N_SAMPLES)")
    ap.add_argument("--reject-threshold", type=float, default=None, help="max contradiction_ratio to keep")
    ap.add_argument("--n-clusters", type=int, default=None, help="fixed cluster count; 0/omit = auto by silhouette")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--skip-rag", action="store_true", help="generate narratives without RAG grounding")
    ap.add_argument("--skip-eval", action="store_true", help="do not run the MCDA stage")
    ap.add_argument("--sample-only", action="store_true", help="run stage 1 only (no LLM at all)")
    ap.add_argument("--smoke", action="store_true", help="cheap end-to-end: N=8, k=3, no RAG")
    ap.add_argument("--max-workers", type=int, default=4, help="narrative-gen concurrency (lower = gentler on rate limits)")
    ap.add_argument("--narrative-mode", choices=["full", "short", "neutral"], default="short",
                    help="full=baseline prompt, short=Andrew less-text, neutral=non-leading prompt")
    ap.add_argument("--model", default=None, help="chat model for narratives (e.g. gpt-5.4 → pooled across endpoints)")
    ap.add_argument("--landscape-space", choices=["config", "narrative"], default="config",
                    help="UMAP/cluster geometry: config=manifestation recipe (default), narrative=prose embeddings")
    ap.add_argument("--outdir", default=DATA_DIR)
    args = ap.parse_args()

    n_samples = args.n_samples
    n_clusters = args.n_clusters
    skip_rag = args.skip_rag
    if args.smoke:
        n_samples = n_samples or 8
        n_clusters = 3 if n_clusters is None else n_clusters
        skip_rag = True

    run(
        n_samples=n_samples,
        reject_threshold=args.reject_threshold,
        n_clusters=n_clusters,
        seed=args.seed,
        skip_rag=skip_rag,
        skip_eval=args.skip_eval,
        sample_only=args.sample_only,
        max_workers=args.max_workers,
        narrative_mode=args.narrative_mode,
        model=args.model,
        landscape_space=args.landscape_space,
        outdir=args.outdir,
    )


if __name__ == "__main__":
    main()
