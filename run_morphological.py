"""Functional morphological (Zwicky) scenario pipeline — coexists with the BOM/CIB path.

functional.run (extract functions + competing directions, CCA, sample consistent configs)
-> short narratives -> config-space clustering -> UMAP landscape -> MCDA on representatives.
All outputs carry a *_zwicky suffix.

Usage:
  uv run python run_morphological.py                       # full (Azure + KB)
  uv run python run_morphological.py --n-samples 12        # cheap test
  uv run python run_morphological.py --extract-only        # extraction + CCA + sampling, no narratives
"""
from __future__ import annotations

import argparse
import json
import logging
import os

from src import config
from src.pipeline import domain, functional, landscape, scenario_gen
from src.pipeline.clustering import cluster_and_select, config_matrix

DATA = "data/outputs"


def _p(name):
    return os.path.join(DATA, name)


def run(n_samples=None, reject_threshold=None, n_clusters=None, model="gpt-5.4",
        max_workers=6, narrative_mode="short", extract_only=False, skip_eval=False,
        skip_extract=False, cca_mode="contrastive", profile=None, collection=None,
        output_dir=None):
    n_clusters = config.COMBI_N_CLUSTERS if n_clusters is None else n_clusters
    # Docking knobs: a different KB is docked by passing its collection + a separate output
    # dir (and optionally a pre-derived profile). Defaults reproduce the primary-KB run.
    data_dir = output_dir or DATA
    os.makedirs(data_dir, exist_ok=True)

    def p(name):
        return os.path.join(data_dir, name)

    explicit_coll = collection is not None
    coll_arg = collection if explicit_coll else "auto"

    # 0. Ensure a DomainProfile (derive from the docked KB on first run). This is what makes
    #    the pipeline domain-agnostic — no domain term is hardwired in any downstream prompt.
    if profile is None:
        try:
            profile = domain.load_profile()
        except FileNotFoundError:
            print("No domain profile yet — deriving from the docked KB ...")
            profile = domain.run(model=model, output_dir=data_dir, collection=coll_arg)
    print(f"  domain: {profile.domain!r} (horizon {profile.horizon}, actor {profile.actor!r})")

    # 1. functional extraction + CCA + CCA-consistent sampling (reuse if requested)
    if skip_extract:
        print("--skip-extract: reusing existing *_zwicky extraction + configs")
    else:
        functional.run(output_dir=data_dir, n_samples=n_samples, reject_threshold=reject_threshold,
                       model=model, max_workers=max_workers, cca_mode=cca_mode, profile=profile,
                       collection=coll_arg)

    seed_path, morph_path = p("combinatorial_state_zwicky.json"), p("morphbox_zwicky_state.json")
    cib_path, merge_path = p("cib_state_zwicky.json"), p("functional_merge_state.json")
    scen_path = p("scenario_state_zwicky.json")
    reps_path = p("scenario_state_zwicky_representatives.json")
    land_path, final_path = p("landscape_state_zwicky.json"), p("final_analysis_zwicky.json")

    if extract_only:
        print("--extract-only: stopped after sampling.")
        return {"seed": seed_path}

    # 2. short narratives (geometry comes from configs, so length/style is free)
    if explicit_coll:
        coll = collection
    else:
        try:
            from src.rag import get_collection
            coll = get_collection()
        except Exception as e:  # noqa: BLE001
            print(f"  no KB collection ({e}) — narratives without RAG")
            coll = None
    print("\n[narratives] generating ...", flush=True)
    scenario_gen.run(consistency_state_path=seed_path, morphbox_state_path=morph_path,
                     cib_state_path=cib_path, merge_state_path=merge_path, output_path=scen_path,
                     narrative_mode=narrative_mode, max_workers=max_workers, collection=coll,
                     model=model, profile=profile)

    # 3. config-space clustering (the honest geometry)
    scenarios = json.load(open(scen_path))["scenarios"]
    ids = [s["id"] for s in scenarios]
    vocab = [m["id"] for m in json.load(open(morph_path))["all_manifestations"]]
    geom = config_matrix(scenarios, vocab)
    cl = cluster_and_select(geom, ids, k=(n_clusters if n_clusters and n_clusters > 0 else None),
                            k_range=config.COMBI_CLUSTER_K_RANGE, seed=config.COMBI_SEED)
    cby, reps = dict(zip(ids, cl["labels"])), set(cl["representative_ids"])
    print(f"  config-space: k={cl['k']} silhouette={cl['silhouette']} representatives={len(reps)}")

    # 4. UMAP landscape on the config geometry
    ls = landscape.run(scenario_state_path=scen_path, output_path=land_path,
                       consistency_state_path=seed_path, embeddings=geom)
    for pt in ls.get("points", []):
        pt["cluster"] = int(cby.get(pt["scenario_id"], -1))
        pt["is_representative"] = pt["scenario_id"] in reps
    ls.setdefault("metadata", {}).update(
        {"method": "functional_zwicky", "geometry": "config", "n_clusters": cl["k"], "silhouette": cl["silhouette"]})

    # 4b. interpretable PCA projection + parallel-coords + honest structure verdict.
    #     Replaces the meaningless UMAP axes for navigation (UMAP x,y stay as a baseline).
    try:
        from src.pipeline import projection
        morph = json.load(open(morph_path))
        try:
            merge = json.load(open(merge_path))
            dnames = {d["id"]: d.get("name", d["id"]) for d in merge.get("unified_drivers", [])}
        except Exception:  # noqa: BLE001
            dnames = None
        proj = projection.project_config(scenarios, morph, driver_names=dnames, seed=config.COMBI_SEED)
        for pt in ls.get("points", []):
            xy = proj["coords"].get(pt["scenario_id"])
            if xy:
                pt["cx"], pt["cy"] = xy
        ls["axes"], ls["structure"], ls["parcoords"] = proj["axes"], proj["structure"], proj["parcoords"]
        print(f"  projection: {ls['structure']['verdict']} "
              f"(PC1 {ls['axes']['pc1']['share']:.0%}, silhouette {ls['structure']['best_silhouette']})")
        # Continuum-native representatives: when the field is a continuum (the honest verdict for
        # this domain), sample scenarios evenly ALONG the labelled PC1 axis instead of taking
        # KMeans "archetype" centroids that don't exist. KMeans labels stay as a diagnostic only.
        axis_reps = projection.representatives_along_axis(proj["coords"], k=min(6, len(scenarios)))
        if axis_reps:
            reps = set(axis_reps)
            for pt in ls.get("points", []):
                pt["is_representative"] = pt["scenario_id"] in reps
            ls["metadata"]["representative_mode"] = "continuum_axis_pc1"
            print(f"  representatives: {len(reps)} sampled along PC1 (continuum-native; KMeans retired)")
    except Exception as e:  # noqa: BLE001
        print(f"  projection failed ({e}); landscape written without PCA axes (KMeans reps kept).")

    json.dump(ls, open(land_path, "w"), indent=2)

    # 5. representatives + MCDA
    json.dump({"scenarios": [s for s in scenarios if s["id"] in reps]}, open(reps_path, "w"), indent=2)
    if not skip_eval:
        try:
            from src.pipeline import evaluation
            print(f"\n[MCDA] on {len(reps)} representatives ...", flush=True)
            evaluation.run(scenario_state_path=reps_path, merge_state_path=merge_path,
                           kb_state_path=p("kb_state.json"), output_path=final_path,
                           cib_state_path=cib_path, profile=profile, collection=coll_arg)
        except Exception as e:  # noqa: BLE001
            print(f"  MCDA failed ({e}); other *_zwicky outputs still written.")

    print("\nDone (Zwicky path). Outputs:")
    for path in (morph_path, p("cca_state.json"), seed_path, scen_path, land_path, final_path):
        print(f"  {'✓' if os.path.exists(path) else '·'} {path}")
    return {"morphbox": morph_path, "scenarios": scen_path, "landscape": land_path}


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Functional morphological (Zwicky) scenario pipeline")
    ap.add_argument("--n-samples", type=int, default=None)
    ap.add_argument("--reject-threshold", type=float, default=None,
                    help="max contradiction_ratio to keep; omit = auto-calibrate to the "
                         "contradiction distribution so the CCA filter actually bites")
    ap.add_argument("--n-clusters", type=int, default=None, help="0/omit = auto by silhouette")
    ap.add_argument("--model", default="gpt-5.4", help="chat model (gpt-5.4 = pooled across endpoints)")
    ap.add_argument("--max-workers", type=int, default=6)
    ap.add_argument("--narrative-mode", choices=["full", "short", "neutral"], default="short")
    ap.add_argument("--cca-mode", choices=["absolute", "contrastive"], default="contrastive",
                    help="CCA elicitation: contrastive flips the prior toward tension and forces "
                         "the scores to spread (breaks the LLM positivity bias; default)")
    ap.add_argument("--extract-only", action="store_true", help="extraction + CCA + sampling only")
    ap.add_argument("--skip-extract", action="store_true", help="reuse existing *_zwicky extraction + configs")
    ap.add_argument("--skip-eval", action="store_true")
    args = ap.parse_args()
    run(n_samples=args.n_samples, reject_threshold=args.reject_threshold, n_clusters=args.n_clusters,
        model=args.model, max_workers=args.max_workers, narrative_mode=args.narrative_mode,
        extract_only=args.extract_only, skip_eval=args.skip_eval, skip_extract=args.skip_extract,
        cca_mode=args.cca_mode)


if __name__ == "__main__":
    main()
