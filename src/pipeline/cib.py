"""Cross-Impact Balance (CIB) Matrix pipeline step.

Supports two modes:
- Single-LLM (legacy): One LLM call per pair
- Panel mode (Multi-Perspective Expert Panel): Multiple expert personas score
  each pair independently, then median-aggregated. Produces persona_scores per
  cell for downstream Monte Carlo consistency analysis.

Input: data/outputs/merge_state.json
Output: data/outputs/cib_state.json
"""

from __future__ import annotations

import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import logging

from src.llm import safe_chat_json, validated_chat_json
from src.models.drivers import TechDriver
from src.models.llm_responses import CIBResponse
from src.models.scenarios import CIBEntry, PersonaScore
from src.models.domain import DomainProfile
from src.prompts.cib import CIB_EVALUATE
from src.prompts.personas import PERSONAS
from src.rag import format_rag_chunks, retrieve

log = logging.getLogger(__name__)


def _evaluate_single(
    i: int,
    j: int,
    da: TechDriver,
    db: TechDriver,
    prompt: str,
    model: str | None,
) -> tuple[int, int, str, PersonaScore]:
    """Single persona evaluation of one driver pair."""
    try:
        result = validated_chat_json(prompt, CIBResponse, model=model)
    except Exception:
        log.warning("CIB validation failed for pair (%d,%d), falling back to safe_chat_json", i, j)
        raw = safe_chat_json(prompt, model=model)
        result = CIBResponse.model_validate(raw) if raw else CIBResponse(inhibiting_score=0, promoting_score=0)
    net = max(-3, min(3, result.promoting_score - result.inhibiting_score))
    reasoning = (
        f"Pro({result.promoting_score}): {result.promoting_reasoning} "
        f"| Inh({result.inhibiting_score}): {result.inhibiting_reasoning}"
    )
    return i, j, "single", PersonaScore(
        persona_id="single",
        model_used=model or "",
        promoting_score=result.promoting_score,
        inhibiting_score=result.inhibiting_score,
        net_score=net,
        reasoning=reasoning,
        source_chunk_ids=result.source_chunk_ids_used,
    )


def _evaluate_persona(
    i: int,
    j: int,
    prompt: str,
    persona: dict,
) -> tuple[int, int, str, PersonaScore]:
    """One persona's evaluation of one driver pair."""
    try:
        result = validated_chat_json(
            prompt, CIBResponse,
            system=persona["system"],
            model=persona["model"],
            temperature=0.3,
        )
    except Exception:
        log.warning("CIB validation failed for pair (%d,%d) persona %s, falling back", i, j, persona["id"])
        raw = safe_chat_json(prompt, system=persona["system"], model=persona["model"], temperature=0.3)
        result = CIBResponse.model_validate(raw) if raw else CIBResponse(inhibiting_score=0, promoting_score=0)
    net = max(-3, min(3, result.promoting_score - result.inhibiting_score))
    reasoning = (
        f"Pro({result.promoting_score}): {result.promoting_reasoning} "
        f"| Inh({result.inhibiting_score}): {result.inhibiting_reasoning}"
    )
    return i, j, persona["id"], PersonaScore(
        persona_id=persona["id"],
        model_used=persona["model"],
        promoting_score=result.promoting_score,
        inhibiting_score=result.inhibiting_score,
        net_score=net,
        reasoning=reasoning,
        source_chunk_ids=result.source_chunk_ids_used,
    )


_ROUND2_SUPPLEMENT = """
ROUND 2 — DELPHI REVISION:
In Round 1, the panel median net score for this pair was {median_net}.
The most divergent panelist ({outlier_id}) scored net={outlier_net} with this reasoning:
{outlier_reasoning}

Reconsider your assessment in light of this information. You may revise your scores
or keep them — but if you keep them, briefly explain why the outlier's argument
does not change your view.
"""


def _aggregate_panel(scores: list[PersonaScore]) -> tuple[int, float, str]:
    """Aggregate persona scores into consensus score."""
    nets = [s.net_score for s in scores]
    median = statistics.median(nets)
    impact = round(median)
    std = statistics.stdev(nets) if len(nets) > 1 else 0.0

    if std < 0.5:
        consensus = "strong"
    elif std < 1.0:
        consensus = "moderate"
    else:
        consensus = "divergent"

    return impact, std, consensus


def _find_outlier(scores: list[PersonaScore]) -> PersonaScore:
    """Find the persona whose net score is furthest from the median."""
    nets = [s.net_score for s in scores]
    median = statistics.median(nets)
    return max(scores, key=lambda s: abs(s.net_score - median))


def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    output_path: str = "data/outputs/cib_state.json",
    collection=None,
    model: str | None = None,
    max_workers: int = 12,
    subset_n: int | None = None,
    panel_mode: bool = True,
    driver_ids: list[str] | None = None,
    delphi_rounds: int = 2,
    profile: DomainProfile | None = None,
) -> dict:
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    pkw = profile.prompt_kwargs()
    with open(merge_state_path) as f:
        merge_state = json.load(f)

    all_drivers = [TechDriver(**d) for d in merge_state["unified_drivers"]]

    if driver_ids:
        id_set = set(driver_ids)
        drivers = [d for d in all_drivers if d.id in id_set]
        print(f"  Using {len(drivers)} pre-selected drivers", flush=True)
    elif subset_n and subset_n < len(all_drivers):
        drivers = all_drivers[:subset_n]
        print(f"  Subset mode: using first {subset_n} of {len(all_drivers)} drivers", flush=True)
    else:
        drivers = all_drivers
    n = len(drivers)

    matrix = [[0] * n for _ in range(n)]
    driver_ids = [d.id for d in drivers]
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]

    pair_prompts: dict[tuple[int, int], str] = {}
    for i, j in pairs:
        rag_text = ""
        if collection is not None:
            query = (
                f"relationship {drivers[i].name} {drivers[j].name} "
                f"{drivers[i].description[:80]} {drivers[j].description[:80]} "
                f"enables inhibits dependency interaction"
            )
            chunks = retrieve(collection, query, pool="trend", n=3)
            rag_text = format_rag_chunks(chunks)
        pair_prompts[(i, j)] = CIB_EVALUATE.format(
            driver_a_name=drivers[i].name,
            driver_a_description=drivers[i].description[:150],
            driver_b_name=drivers[j].name,
            driver_b_description=drivers[j].description[:150],
            rag_chunks=rag_text,
            **pkw,
        )

    results: dict[tuple[int, int], list[PersonaScore]] = {p: [] for p in pairs}

    if panel_mode:
        personas = [p.model_dump() for p in profile.personas] if profile.personas else PERSONAS
        total_tasks = len(pairs) * len(personas)
        print(f"  Round 1: {len(personas)} personas x {len(pairs)} pairs = {total_tasks} evaluations", flush=True)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for i, j in pairs:
                for persona in personas:
                    fut = pool.submit(
                        _evaluate_persona, i, j, pair_prompts[(i, j)], persona,
                    )
                    futures[fut] = (i, j, persona["id"])

            done = 0
            for future in as_completed(futures):
                ri, rj, pid, score = future.result()
                results[(ri, rj)].append(score)
                done += 1
                if done % 50 == 0:
                    print(f"  Round 1 progress: {done}/{total_tasks}", flush=True)

        # Round 2: share outlier reasoning and re-score
        if delphi_rounds >= 2:
            r1_stds = []
            for pair_key, scores in results.items():
                nets = [s.net_score for s in scores]
                r1_stds.append(statistics.stdev(nets) if len(nets) > 1 else 0.0)
            divergent_pairs = [(p, s) for p, s in zip(pairs, r1_stds) if s >= 0.5]
            print(f"  Round 2: re-scoring {len(divergent_pairs)} divergent pairs (std >= 0.5)", flush=True)

            r2_results: dict[tuple[int, int], list[PersonaScore]] = {}

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for (i, j), _ in divergent_pairs:
                    r1_scores = results[(i, j)]
                    median_net = round(statistics.median([s.net_score for s in r1_scores]))
                    outlier = _find_outlier(r1_scores)
                    supplement = _ROUND2_SUPPLEMENT.format(
                        median_net=median_net,
                        outlier_id=outlier.persona_id,
                        outlier_net=outlier.net_score,
                        outlier_reasoning=outlier.reasoning,
                    )
                    r2_prompt = pair_prompts[(i, j)] + supplement

                    for persona in personas:
                        fut = pool.submit(
                            _evaluate_persona, i, j, r2_prompt, persona,
                        )
                        futures[fut] = (i, j, persona["id"])

                done = 0
                for future in as_completed(futures):
                    ri, rj, pid, score = future.result()
                    r2_results.setdefault((ri, rj), []).append(score)
                    done += 1
                    if done % 50 == 0:
                        print(f"  Round 2 progress: {done}/{len(divergent_pairs) * len(personas)}", flush=True)

            for pair_key, r2_scores in r2_results.items():
                results[pair_key] = r2_scores

            print(f"  Delphi Round 2 complete: {len(r2_results)} pairs re-scored", flush=True)
    else:
        total_tasks = len(pairs)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _evaluate_single, i, j, drivers[i], drivers[j],
                    pair_prompts[(i, j)], model,
                ): (i, j)
                for i, j in pairs
            }
            done = 0
            for future in as_completed(futures):
                ri, rj, _, score = future.result()
                results[(ri, rj)].append(score)
                done += 1
                if done % 20 == 0:
                    print(f"  CIB progress: {done}/{total_tasks}")

    entries: list[dict] = []
    persona_scores_map: dict[str, list[int]] = {}

    for (i, j), scores in results.items():
        if panel_mode and len(scores) > 1:
            impact, std, consensus = _aggregate_panel(scores)
        else:
            impact = scores[0].net_score if scores else 0
            std = 0.0
            consensus = "single"

        matrix[i][j] = impact

        all_source_ids = []
        all_reasoning = []
        for s in scores:
            all_source_ids.extend(s.source_chunk_ids)
            all_reasoning.append(f"[{s.persona_id}] {s.reasoning}")

        entry = CIBEntry(
            driver_a_id=drivers[i].id,
            driver_b_id=drivers[j].id,
            impact_score=impact,
            reasoning=" | ".join(all_reasoning),
            source_chunk_ids=list(set(all_source_ids)),
            persona_scores=scores,
            score_std=round(std, 2),
            consensus_level=consensus,
        )
        entries.append(entry.model_dump(mode="json"))

        cell_key = f"{i},{j}"
        persona_scores_map[cell_key] = [s.net_score for s in scores]

    influence = {d.id: sum(matrix[i]) for i, d in enumerate(drivers)}
    dependence = {
        d.id: sum(matrix[j][i] for j in range(n)) for i, d in enumerate(drivers)
    }

    cib_state = {
        "matrix": matrix,
        "driver_ids": driver_ids,
        "driver_names": [d.name for d in drivers],
        "entries": entries,
        "influence": influence,
        "dependence": dependence,
        "persona_scores_map": persona_scores_map,
        "panel_metadata": {
            "mode": "multi_perspective_panel" if panel_mode else "single",
            "delphi_rounds": delphi_rounds if panel_mode else 1,
            "personas": [
                {"id": p["id"], "name": p["name"], "model": p["model"]}
                for p in (PERSONAS if panel_mode else [])
            ],
            "n_personas": len(PERSONAS) if panel_mode else 1,
        },
    }

    with open(output_path, "w") as f:
        json.dump(cib_state, f, indent=2)

    # CIB matrix diagnostics
    flat_scores = [matrix[i][j] for i in range(n) for j in range(n) if i != j]
    n_negative = sum(1 for s in flat_scores if s < 0)
    n_zero = sum(1 for s in flat_scores if s == 0)
    n_positive = sum(1 for s in flat_scores if s > 0)
    n_total = len(flat_scores)
    print(f"  CIB matrix: {n_negative} negative ({n_negative/n_total*100:.1f}%), "
          f"{n_zero} zero ({n_zero/n_total*100:.1f}%), "
          f"{n_positive} positive ({n_positive/n_total*100:.1f}%)", flush=True)
    if n_negative / n_total < 0.10:
        print(f"  WARNING: Only {n_negative/n_total*100:.1f}% negative entries. "
              f"Real CIB matrices typically have 20-30% negative (Weimer-Jehle 2006).", flush=True)

    if panel_mode:
        stds = [e["score_std"] for e in entries]
        divergent = sum(1 for s in stds if s >= 1.0)
        print(f"  Panel consensus: {sum(1 for s in stds if s < 0.5)} strong, "
              f"{sum(1 for s in stds if 0.5 <= s < 1.0)} moderate, {divergent} divergent", flush=True)

    return cib_state
