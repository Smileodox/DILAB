"""Fast E2E pipeline run with top-N driver subset.

Runs: Manifestations -> CIB -> Consistency -> Scenarios -> Landscape -> Evaluation
Skips KB/BOM/Trends/Merge by default (uses existing merge_state.json).

Pass --redo-trends to re-run the KB coverage-gap trend scanner + merge first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config import CIB_MODEL, CIB_MC_SAMPLES, CIB_MC_RESTARTS, SCENARIO_N_SEEDS, SCENARIO_MODEL
from src.llm import safe_chat_json, validated_chat_json
from src.models.llm_responses import ManifestationResponse
from src.models.drivers import TechDriver
from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import cib, morphological, scenario_gen, evaluation, strategic_framing
from src.pipeline.morphological import validate_manifestation_ordering, _OPTIMISTIC_ANCHOR, _PESSIMISTIC_ANCHOR
from src.prompts.morphological import MANIFESTATION_DETERMINE
from src.rag import get_collection, retrieve, format_rag_chunks

SUBSET_N = 14
CIB_WORKERS = 8
MANIF_WORKERS = 4
DATA_DIR = "data/outputs"


def log(msg: str):
    print(msg, flush=True)


def select_top_drivers(merge_path: str, n: int) -> list[TechDriver]:
    """Evidence-weighted stratified selection.

    Balances validation status (origin) with evidence depth (source count)
    so that well-evidenced trend drivers are not systematically excluded.
    """
    with open(merge_path) as f:
        all_drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]

    max_sources = max((len(d.source_chunk_ids) for d in all_drivers), default=1) or 1
    # trend slightly outweighs pure-BOM to ensure environment drivers enter the morphological box
    ORIGIN_SCORE = {"both": 1.0, "bom": 0.3, "trend": 0.4}

    def _score(d: TechDriver) -> float:
        origin = ORIGIN_SCORE.get(d.origin.value, 0.3)
        evidence = len(d.source_chunk_ids) / max_sources
        return round(0.5 * origin + 0.5 * evidence, 3)

    scored = [(d, _score(d)) for d in all_drivers]
    scored.sort(key=lambda t: (-t[1], t[0].name))  # deterministic tiebreaker on name

    selected = [d for d, _ in scored[:n]]
    log(f"Selected {len(selected)}/{len(all_drivers)} drivers (evidence-weighted):")
    for d, s in scored[:n]:
        src_n = len(d.source_chunk_ids)
        log(f"  {s:.3f}  [{d.origin.value:5s}|{d.confidence.value:6s}] {d.name[:55]}  ({src_n} src)")
    log("  ---")
    for d, s in scored[n:n + 3]:
        src_n = len(d.source_chunk_ids)
        log(f"  {s:.3f}  [{d.origin.value:5s}|{d.confidence.value:6s}] {d.name[:55]}  ({src_n} src)  <- next")
    return selected


def generate_manifestations_parallel(
    drivers: list[TechDriver], collection, max_workers: int = MANIF_WORKERS, profile=None
) -> dict:
    # MANIFESTATION_DETERMINE is a neutralized prompt ({domain}/{horizon}/{manifestation_example});
    # inject the docked domain profile so the call is domain-agnostic (was hardwired to spectrum).
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    pkw = profile.prompt_kwargs()
    manif_system = (f"You are determining technology manifestations for {pkw['domain']} "
                    "foresight. Be specific and domain-grounded.")

    all_manifestations: list[DriverManifestation] = []
    manifestation_map: dict[str, list[str]] = {}

    def _gen_one(driver: TechDriver) -> tuple[str, list[DriverManifestation]]:
        chunks = retrieve(collection, f"{driver.name} {driver.description[:100]}", n=5)
        rag_text = format_rag_chunks(chunks)

        prompt = MANIFESTATION_DETERMINE.format(
            driver_name=driver.name,
            driver_description=driver.description,
            driver_origin=driver.origin.value,
            driver_confidence=driver.confidence.value,
            rag_chunks=rag_text,
            **pkw,
        )

        try:
            result = validated_chat_json(
                prompt,
                ManifestationResponse,
                system=manif_system,
            )
            manifs = [
                DriverManifestation(
                    driver_id=driver.id,
                    label=m.label,
                    description=m.description,
                    plausibility=m.plausibility,
                    source_chunk_ids=result.source_chunk_ids_used,
                )
                for m in result.manifestations
            ]
        except Exception:
            raw = safe_chat_json(
                prompt,
                system=manif_system,
            )
            manifs = [
                DriverManifestation(
                    driver_id=driver.id,
                    label=m["label"],
                    description=m["description"],
                    plausibility=m.get("plausibility", "medium"),
                    source_chunk_ids=raw.get("source_chunk_ids_used", []),
                )
                for m in raw.get("manifestations", [])
            ]
        return driver.id, manifs

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_gen_one, d): d for d in drivers}
        done = 0
        for future in as_completed(futures):
            driver = futures[future]
            driver_id, manifs = future.result()
            all_manifestations.extend(manifs)
            manifestation_map[driver_id] = [m.id for m in manifs]
            done += 1
            log(f"  Manifestations {done}/{len(drivers)}: {driver.name[:40]} -> {len(manifs)} states")

    morphbox_state = {
        "drivers": [d.id for d in drivers],
        "manifestations": manifestation_map,
        "all_manifestations": [m.model_dump(mode="json") for m in all_manifestations],
    }

    # Validate and auto-fix optimistic->pessimistic ordering (critical for hill-climbing)
    by_driver: dict[str, list[DriverManifestation]] = {}
    for m in all_manifestations:
        by_driver.setdefault(m.driver_id, []).append(m)

    driver_name_by_id = {d.id: d.name for d in drivers}
    reordered_count = 0
    for driver_id, manifs in by_driver.items():
        ordered = [m for mid in manifestation_map[driver_id] for m in manifs if m.id == mid]
        result = validate_manifestation_ordering(ordered, driver_name_by_id.get(driver_id, driver_id))
        if result is None:
            from src.llm import embed
            import numpy as np
            texts = [f"{m.label}: {m.description}" for m in ordered]
            all_texts = texts + [_OPTIMISTIC_ANCHOR, _PESSIMISTIC_ANCHOR]
            embeddings = embed(all_texts)
            manif_vecs = np.array(embeddings[:len(texts)])
            opt_vec = np.array(embeddings[-2])
            pes_vec = np.array(embeddings[-1])
            opt_vec = opt_vec / np.linalg.norm(opt_vec)
            pes_vec = pes_vec / np.linalg.norm(pes_vec)
            norms = np.linalg.norm(manif_vecs, axis=1, keepdims=True)
            manif_vecs = manif_vecs / norms
            scores = (manif_vecs @ opt_vec - manif_vecs @ pes_vec).tolist()
            sorted_manifs = [m for _, m in sorted(zip(scores, ordered), reverse=True)]
            manifestation_map[driver_id] = [m.id for m in sorted_manifs]
            reordered_count += 1
            log(f"  -> Auto-reordered: {driver_name_by_id.get(driver_id, driver_id)[:50]}")
    if reordered_count:
        log(f"  -> {reordered_count} driver(s) auto-reordered")
    else:
        log("  -> Manifestation ordering validated (optimistic->pessimistic)")

    out_path = os.path.join(DATA_DIR, "morphbox_state.json")
    with open(out_path, "w") as f:
        json.dump(morphbox_state, f, indent=2)

    log(f"  -> {len(all_manifestations)} manifestations for {len(drivers)} drivers")
    return morphbox_state


def run_consistency(morphbox_state: dict, cib_state: dict) -> dict:
    morph_box = MorphologicalBox(
        drivers=morphbox_state["drivers"],
        manifestations=morphbox_state["manifestations"],
        all_manifestations=[
            DriverManifestation(**m) for m in morphbox_state["all_manifestations"]
        ],
    )

    cib_drivers = set(cib_state["driver_ids"])
    shared_drivers = [d for d in morph_box.drivers if d in cib_drivers]

    filtered_box = MorphologicalBox(
        drivers=shared_drivers,
        manifestations={d: morph_box.manifestations[d] for d in shared_drivers},
        all_manifestations=[
            m for m in morph_box.all_manifestations if m.driver_id in cib_drivers
        ],
    )

    driver_index = {did: i for i, did in enumerate(cib_state["driver_ids"])}

    persona_scores_map = cib_state.get("persona_scores_map", {})
    if persona_scores_map:
        log(f"  Monte Carlo mode: {CIB_MC_SAMPLES} samples x {CIB_MC_RESTARTS} restarts")
        all_configs = morphological.find_consistent_configs_monte_carlo(
            filtered_box,
            persona_scores_map,
            driver_index,
            n_mc_samples=CIB_MC_SAMPLES,
            n_restarts_per_sample=CIB_MC_RESTARTS,
            seed=42,
        )
    else:
        all_configs = morphological.find_consistent_configs(
            filtered_box,
            cib_state["matrix"],
            driver_index,
            n_restarts=10000,
            seed=42,
        )

    n_fixed = len(all_configs)
    log(f"  Found {n_fixed} unique fixed points")

    for c in all_configs:
        c.scenario_type = morphological.infer_scenario_type(c.configuration, filtered_box)

    # Near-consistent neighbors (single-driver flips)
    median_matrix = cib_state["matrix"]
    neighbors = morphological.find_near_consistent_neighbors(
        all_configs, filtered_box, median_matrix, driver_index,
    )
    for nb in neighbors:
        nb.scenario_type = morphological.infer_scenario_type(nb.configuration, filtered_box)
    log(f"  Found {len(neighbors)} near-consistent neighbors")

    # Select seeds: ensure at least one of each reachable type, then fill remaining
    # slots with Hamming-based diversity.
    candidate_pool = list(all_configs) + neighbors
    seeds = morphological.select_scenario_seeds_typed(
        candidate_pool, filtered_box, n=SCENARIO_N_SEEDS, min_hamming=4,
    )

    type_counts: dict[str, int] = {}
    fp_count = sum(1 for s in seeds if s.is_fixed_point)
    for s in seeds:
        type_counts[s.scenario_type] = type_counts.get(s.scenario_type, 0) + 1
    log(f"  Seed types: {type_counts} ({fp_count} fixed points, {len(seeds) - fp_count} near-neighbors)")

    consistency_state = {
        "configs": [
            {
                "id": s.id,
                "configuration": s.configuration,
                "consistency_score": s.consistency_score,
                "is_consistent": s.is_consistent,
                "scenario_type": s.scenario_type,
                "frequency": s.frequency,
                "is_fixed_point": s.is_fixed_point,
                "parent_fixed_point_id": s.parent_fixed_point_id,
                "flipped_driver_id": s.flipped_driver_id,
            }
            for s in seeds
        ],
        "total_fixed_points": n_fixed,
        "total_neighbors": len(neighbors),
        "n_mc_samples": CIB_MC_SAMPLES if persona_scores_map else 0,
    }

    out_path = os.path.join(DATA_DIR, "consistency_state.json")
    with open(out_path, "w") as f:
        json.dump(consistency_state, f, indent=2)

    log(f"  -> {len(seeds)} scenario seeds selected")
    return consistency_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--redo-trends",
        action="store_true",
        help="Re-run KB coverage-gap trend scanner + merge before morphological analysis",
    )
    parser.add_argument(
        "--skip-manif",
        action="store_true",
        help="Skip manifestation generation (use existing morphbox_state.json)",
    )
    args = parser.parse_args()

    t_start = time.time()

    log("=" * 60)
    log(f"SUBSET E2E RUN (top {SUBSET_N} drivers)")
    log("=" * 60)

    if args.redo_trends:
        log("=" * 60)
        log("STEP 0a: Trend Scanning (KB coverage-gap)")
        log("=" * 60)
        t0 = time.time()
        from src.pipeline import trends, merge
        trends.run()
        log(f"  Time: {time.time() - t0:.0f}s\n")

        log("=" * 60)
        log("STEP 0b: Merge (BOM + Trends)")
        log("=" * 60)
        t0 = time.time()
        merge.run()
        log(f"  Time: {time.time() - t0:.0f}s\n")

    merge_path = os.path.join(DATA_DIR, "merge_state.json")
    drivers = select_top_drivers(merge_path, SUBSET_N)

    collection = get_collection()
    log(f"KB collection: {collection.count()} chunks\n")

    # Step 1: Manifestations (parallel)
    if args.skip_manif:
        log("=" * 60)
        log("STEP 1: Manifestations (SKIPPED — using existing morphbox_state.json)")
        log("=" * 60)
        with open(os.path.join(DATA_DIR, "morphbox_state.json")) as f:
            morphbox_state = json.load(f)
        log(f"  Loaded {len(morphbox_state['all_manifestations'])} manifestations for {len(morphbox_state['drivers'])} drivers\n")
    else:
        log("=" * 60)
        log("STEP 1: Manifestations (parallel)")
        log("=" * 60)
        t0 = time.time()
        morphbox_state = generate_manifestations_parallel(drivers, collection, MANIF_WORKERS)
        log(f"  Time: {time.time() - t0:.0f}s\n")

    # Step 2: CIB Matrix (parallel)
    log("=" * 60)
    log("STEP 2: CIB Matrix (parallel)")
    log("=" * 60)
    t0 = time.time()
    cib_state = cib.run(
        collection=collection,
        model=CIB_MODEL,
        max_workers=CIB_WORKERS,
        panel_mode=True,
        driver_ids=[d.id for d in drivers],
    )
    log(f"  Time: {time.time() - t0:.0f}s\n")

    # Step 3: Consistency Analysis + Near-Neighbors (no API calls)
    log("=" * 60)
    log("STEP 3: Consistency Analysis + Near-Neighbors")
    log("=" * 60)
    t0 = time.time()
    consistency_state = run_consistency(morphbox_state, cib_state)
    log(f"  Time: {time.time() - t0:.1f}s\n")

    # Step 4: Scenario Generation (parallel)
    log("=" * 60)
    log("STEP 4: Scenario Generation (parallel)")
    log("=" * 60)
    t0 = time.time()
    scenario_gen.run(collection=collection, model=SCENARIO_MODEL)
    log(f"  Time: {time.time() - t0:.0f}s\n")

    # Step 4.5: Scenario Landscape (embeddings + UMAP)
    log("=" * 60)
    log("STEP 4.5: Scenario Landscape")
    log("=" * 60)
    t0 = time.time()
    try:
        from src.pipeline import landscape
        landscape.run()
        log(f"  Time: {time.time() - t0:.1f}s\n")
    except ImportError:
        log("  Skipped (umap-learn not installed)\n")

    # Step 5: Evaluation + MCDA
    log("=" * 60)
    log("STEP 5: Evaluation + MCDA")
    log("=" * 60)
    t0 = time.time()
    consistency_scores = [c["consistency_score"] for c in consistency_state["configs"]]
    evaluation.run(consistency_scores=consistency_scores)
    log(f"  Time: {time.time() - t0:.0f}s\n")

    # Step 6: Strategic Framing
    log("=" * 60)
    log("STEP 6: Strategic Framing")
    log("=" * 60)
    t0 = time.time()
    strategic_framing.run()
    log(f"  Time: {time.time() - t0:.0f}s\n")

    elapsed = time.time() - t_start
    log("=" * 60)
    log(f"ALL DONE in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    log("=" * 60)

    for fname in [
        "morphbox_state.json",
        "cib_state.json",
        "consistency_state.json",
        "scenario_state.json",
        "landscape_state.json",
        "final_analysis.json",
        "strategic_framing.json",
    ]:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            log(f"  {fname:35s} {size // 1024:5d} KB")
        else:
            log(f"  {fname:35s} MISSING")

    log(f"\nStart dashboard: uv run uvicorn web.app:app --reload")


if __name__ == "__main__":
    main()
