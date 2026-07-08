"""Run the ENTIRE foresight pipeline from the docked knowledge base in ONE command.

    uv run python run_full.py                     # full run on the docked KB (+ arXiv augment)
    uv run python run_full.py --skip-arxiv        # full run, no KB augmentation
    uv run python run_full.py --arxiv-query "6G spectrum sharing"   # override arXiv query
    uv run python run_full.py --dry-run           # print the stage plan, run nothing

Chains the CURRENT (src/pipeline) stages end-to-end — this is the runnable successor to the
stale notebook pipeline. Reuses the proven helpers in scripts/run_subset.py and adds the two
new integrations at their natural spots: arXiv KB augmentation up front, temporal/DVI at the end.

Stages:
  0. [opt] arXiv augmentation   arxiv_ingest      -> adds papers to the KB (+ kb_state.json)
  1. Trend scanning             trends.run        -> trend_state.json      (KB coverage-gap)
  2. Merge drivers              merge.run         -> merge_state.json      (BOM* + trends)
  3. Manifestations             (run_subset)      -> morphbox_state.json
  4. CIB matrix (Delphi panel)  cib.run           -> cib_state.json
  5. Consistency (fixed points) (run_subset)      -> consistency_state.json
  6. Scenario generation        scenario_gen.run  -> scenario_state.json
  7. Landscape                  landscape.run     -> landscape_state.json
  8. Grounded evaluation (MCDA) evaluation.run    -> final_analysis.json   (love's auditor)
  9. Temporal / DVI maturity    temporal.run      -> temporal_state.json   (Adi-inspired axes)
 10. Strategic framing          strategic_framing -> strategic_framing.json

  * BOM (product decomposition) is reused from the existing bom_state.json — it decomposes a
    product, not the KB, and bom.py is still a stub. Everything downstream is regenerated.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# scripts/ is not a package — put it on the path so we can reuse run_subset's helpers.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

from run_subset import (  # noqa: E402
    DATA_DIR, SUBSET_N,
    generate_manifestations_parallel, run_consistency, select_top_drivers,
)

def log(msg: str = "") -> None:
    print(msg, flush=True)  # flush so the detached run streams progress live


def _p(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def _merge_into_kb_state(sources: dict, chunks: dict, kb_state_path: str) -> None:
    """Fold arXiv Source/Chunk objects into kb_state.json so traceability resolves them."""
    state = {"sources": {}, "chunks": {}}
    if os.path.exists(kb_state_path):
        with open(kb_state_path) as f:
            state = json.load(f)
    state.setdefault("sources", {})
    state.setdefault("chunks", {})
    for sid, s in sources.items():
        state["sources"][sid] = s.model_dump(mode="json")
    for cid, c in chunks.items():
        state["chunks"][cid] = c.model_dump(mode="json")
    with open(kb_state_path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _arxiv_query(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    try:
        from src.pipeline.domain import load_profile
        p = load_profile()
        return p.retrieval_queries.get("trends") or p.domain or None
    except Exception as e:  # noqa: BLE001
        log(f"  (could not derive arXiv query from domain profile: {e})")
        return None


def stage(n: int, total: int, title: str) -> float:
    log("\n" + "=" * 64)
    log(f"[{n}/{total}] {title}")
    log("=" * 64)
    return time.time()


def run(skip_arxiv: bool = False, arxiv_query: str | None = None, arxiv_max: int = 25,
        arxiv_categories: list[str] | None = None, n_drivers: int = SUBSET_N,
        skip_trends: bool = False, skip_manif: bool = False,
        dry_run: bool = False) -> dict:
    from src.config import CIB_MODEL, SCENARIO_MODEL
    from src.pipeline import (arxiv_ingest, trends, merge, cib, scenario_gen,
                              landscape, evaluation, temporal, strategic_framing,
                              archetypes, structure)
    from src.rag import get_collection

    plan = [
        ("arXiv augmentation" + (" (SKIPPED)" if skip_arxiv else ""), not skip_arxiv),
        ("Trend scanning (KB coverage-gap)", True),
        ("Merge drivers (BOM + trends)", True),
        ("Manifestations", True),
        ("CIB matrix (Delphi panel)", True),
        ("Consistency (fixed points)", True),
        ("Scenario generation", True),
        ("Landscape", True),
        ("Grounded evaluation (MCDA)", True),
        ("Temporal / DVI maturity", True),
        ("Strategic framing", True),
        ("Combinatorial branch (soft-CIB field)", True),
        ("Archetype extraction (HDBSCAN + ordinal)", True),
        ("Multi-method structure (lens comparison)", True),
    ]
    total = sum(1 for _, on in plan if on)
    if dry_run:
        log("DRY RUN — stage plan (nothing executed):")
        i = 0
        for title, on in plan:
            if not on:
                log(f"   ·  {title}")
                continue
            i += 1
            log(f"  {i:>2}. {title}")
        log(f"\n  n_drivers={n_drivers}  arxiv_max={arxiv_max}  "
            f"arxiv_query={_arxiv_query(arxiv_query)!r}")
        return {"dry_run": True, "stages": total}

    t_start = time.time()
    n = 0

    # --- Stage 0: arXiv augmentation --------------------------------------------------
    if not skip_arxiv:
        query = _arxiv_query(arxiv_query)
        n += 1
        t0 = stage(n, total, f"arXiv augmentation — query={query!r}")
        if not query:
            log("  No query available (no domain profile) — skipping arXiv augmentation.")
        else:
            papers = arxiv_ingest.fetch_arxiv(query, categories=arxiv_categories,
                                              max_results=arxiv_max)
            coll = get_collection()
            res = arxiv_ingest.ingest_papers(
                papers, collection=coll, clear=False,
                state_path=_p("arxiv_kb_state.json"),
            )
            _merge_into_kb_state(res["sources"], res["chunks"], _p("kb_state.json"))
            log(f"  arXiv: {len(papers)} papers → {res['n_chunks']} chunks added "
                f"({len(res['skipped'])} skipped) → KB now {coll.count()} chunks")
        log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 1+2: trends + merge (fresh from the KB, incl. any arXiv chunks) --------
    if skip_trends:
        log("\n[skip] Trends + Merge — reusing existing merge_state.json")
    else:
        n += 1
        t0 = stage(n, total, "Trend scanning (KB coverage-gap)")
        trends.run()
        log(f"  Time: {time.time() - t0:.0f}s")
        n += 1
        t0 = stage(n, total, "Merge drivers (BOM + trends)")
        merge.run()
        log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 3: select drivers + manifestations -------------------------------------
    collection = get_collection()
    log(f"\nKB collection: {collection.count()} chunks")
    drivers = select_top_drivers(_p("merge_state.json"), n_drivers)

    if skip_manif:
        log("\n[skip] Manifestations — reusing existing morphbox_state.json")
        with open(_p("morphbox_state.json")) as f:
            morphbox_state = json.load(f)
    else:
        n += 1
        t0 = stage(n, total, "Manifestations (parallel)")
        morphbox_state = generate_manifestations_parallel(drivers, collection)
        log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 4: CIB matrix (Delphi panel) -------------------------------------------
    n += 1
    t0 = stage(n, total, "CIB matrix (Delphi panel)")
    cib_state = cib.run(collection=collection, model=CIB_MODEL, panel_mode=True,
                        driver_ids=[d.id for d in drivers])
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 5: consistency / fixed points ------------------------------------------
    n += 1
    t0 = stage(n, total, "Consistency (fixed points + neighbors)")
    consistency_state = run_consistency(morphbox_state, cib_state)
    consistency_scores = [c["consistency_score"] for c in consistency_state["configs"]]
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 6: scenario generation -------------------------------------------------
    n += 1
    t0 = stage(n, total, "Scenario generation")
    scenario_gen.run(collection=collection, model=SCENARIO_MODEL)
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 7: landscape -----------------------------------------------------------
    n += 1
    t0 = stage(n, total, "Landscape")
    try:
        landscape.run()
    except Exception as e:  # noqa: BLE001
        log(f"  Landscape skipped ({e})")
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 8: grounded evaluation (love's evidence-grounded auditor -> MCDA) ------
    n += 1
    t0 = stage(n, total, "Grounded evaluation (MCDA)")
    evaluation.run(consistency_scores=consistency_scores,
                   cib_state_path=_p("cib_state.json"))
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 9: temporal / DVI maturity (Adi-inspired axes) -------------------------
    n += 1
    t0 = stage(n, total, "Temporal / DVI maturity")
    temporal.run()
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 10: strategic framing --------------------------------------------------
    n += 1
    t0 = stage(n, total, "Strategic framing")
    try:
        strategic_framing.run()
    except Exception as e:  # noqa: BLE001
        log(f"  Strategic framing skipped ({e})")
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 11: combinatorial branch (equal-standing method: soft-CIB field) -------
    # Reuses the morphbox/cib/merge just written (no second upstream). Produces the *_combi
    # states + the 120-config field the archetype layer clusters.
    n += 1
    t0 = stage(n, total, "Combinatorial branch (soft-CIB field)")
    try:
        import run_combinatorial  # repo-root script
        run_combinatorial.run(skip_rag=False, skip_eval=False)
    except Exception as e:  # noqa: BLE001
        log(f"  Combinatorial branch skipped ({e})")
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 12: archetype extraction (name the dense-core clusters) ----------------
    n += 1
    t0 = stage(n, total, "Archetype extraction (HDBSCAN + ordinal)")
    try:
        arch_state = archetypes.run(model=SCENARIO_MODEL)
        # Colour the combinatorial landscape by archetype: config_labels is index-aligned with the
        # scenarios/points, so stamp each point's `archetype` label (no fragile id join).
        labels = (arch_state or {}).get("config_labels") or []
        lp = _p("landscape_state_combi.json")
        if labels and os.path.exists(lp):
            with open(lp) as f:
                land = json.load(f)
            pts = land.get("points", [])
            if len(pts) == len(labels):
                for i, p in enumerate(pts):
                    p["archetype"] = labels[i]
                with open(lp, "w") as f:
                    json.dump(land, f, indent=2)
    except Exception as e:  # noqa: BLE001
        log(f"  Archetype extraction skipped ({e})")
    log(f"  Time: {time.time() - t0:.0f}s")

    # --- Stage 13: multi-method structure lenses (into the combinatorial landscape) ---
    n += 1
    t0 = stage(n, total, "Multi-method structure (lens comparison)")
    try:
        with open(_p("combinatorial_state.json")) as f:
            combi_cfgs = json.load(f)["configs"]
        with open(_p("morphbox_state.json")) as f:
            morph = json.load(f)
        multi = structure.analyze_multi(structure.configs_to_scenarios(combi_cfgs), morph)
        lp = _p("landscape_state_combi.json")
        if os.path.exists(lp):
            with open(lp) as f:
                land = json.load(f)
            land.setdefault("structure", {})["lenses"] = multi["lenses"]
            land["structure"]["floor"] = multi["floor"]
            with open(lp, "w") as f:
                json.dump(land, f, indent=2)
        log("  Lenses: " + " · ".join(f"{k}={v['silhouette']}" for k, v in multi["lenses"].items()))
    except Exception as e:  # noqa: BLE001
        log(f"  Multi-method structure skipped ({e})")
    log(f"  Time: {time.time() - t0:.0f}s")

    elapsed = time.time() - t_start
    log("\n" + "=" * 64)
    log(f"FULL RUN COMPLETE in {elapsed:.0f}s ({elapsed / 60:.1f} min)")
    log("=" * 64)
    for fname in ["kb_state.json", "arxiv_kb_state.json", "trend_state.json", "merge_state.json",
                  "morphbox_state.json", "cib_state.json", "consistency_state.json",
                  "scenario_state.json", "landscape_state.json", "final_analysis.json",
                  "temporal_state.json", "strategic_framing.json",
                  "scenario_state_combi.json", "landscape_state_combi.json",
                  "final_analysis_combi.json", "archetypes_state.json"]:
        path = _p(fname)
        mark = "OK  " if os.path.exists(path) else "MISS"
        size = f"{os.path.getsize(path)//1024:>5d} KB" if os.path.exists(path) else "     "
        log(f"  [{mark}] {fname:32s} {size}")
    log("\nStart dashboard: uv run uvicorn web.app:app --reload")
    return {"elapsed_s": elapsed}


def main():
    ap = argparse.ArgumentParser(description="Full from-the-KB foresight pipeline (one command)")
    ap.add_argument("--skip-arxiv", action="store_true", help="do not augment the KB with arXiv papers")
    ap.add_argument("--arxiv-query", default=None, help="override the arXiv search query (default: from domain profile)")
    ap.add_argument("--arxiv-max", type=int, default=25, help="max arXiv papers to fetch")
    ap.add_argument("--arxiv-cat", nargs="*", default=None, help="optional arXiv category filter, e.g. cs.NI eess.SP")
    ap.add_argument("--n-drivers", type=int, default=SUBSET_N, help="top-N drivers to carry into the morphological box")
    ap.add_argument("--skip-trends", action="store_true", help="reuse existing merge_state.json (skip trends+merge)")
    ap.add_argument("--skip-manif", action="store_true", help="reuse existing morphbox_state.json (skip manifestations)")
    ap.add_argument("--dry-run", action="store_true", help="print the stage plan and exit")
    args = ap.parse_args()
    run(skip_arxiv=args.skip_arxiv, arxiv_query=args.arxiv_query, arxiv_max=args.arxiv_max,
        arxiv_categories=args.arxiv_cat, n_drivers=args.n_drivers,
        skip_trends=args.skip_trends, skip_manif=args.skip_manif, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
