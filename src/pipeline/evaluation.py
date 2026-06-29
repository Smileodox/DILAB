"""Scenario Evaluation pipeline step with MCDA (AHP + TOPSIS)."""
from __future__ import annotations
import json
import logging
import os

import numpy as np

from src.config import (
    CHROMA_PERSIST_DIR, EVAL_MODEL, MCDA_CRITERIA,
    MCDA_PAIRWISE_DEFAULT, MCDA_CR_THRESHOLD,
)
from src.llm import embed, safe_chat_json
from src.models.scenarios import Scenario
from src.models.evaluation import Assessment, AHPWeights, MCDAResult
from src.models.domain import DomainProfile
from src.models.drivers import TechDriver, DriverConfidence
from src.rag import get_collection
from src.prompts.evaluation import SCENARIO_ASSESS

log = logging.getLogger(__name__)

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}

# Random Index values for AHP consistency check (Saaty, 1980)
_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def compute_scenario_confidences(
    scenarios: list[Scenario],
    driver_by_id: dict[str, TechDriver],
    consistency_scores: list[float] | None = None,
) -> list[float]:
    max_cs = max(consistency_scores) if consistency_scores else 0

    confidences = []
    for i, scenario in enumerate(scenarios):
        driver_confs = []
        for a in scenario.assumptions:
            d = driver_by_id.get(a.driver_id)
            if d:
                driver_confs.append(CONFIDENCE_MAP.get(d.confidence.value, 0.5))
        driver_conf = float(np.mean(driver_confs)) if driver_confs else 0.5

        if consistency_scores and i < len(consistency_scores) and max_cs > 0:
            cib_conf = consistency_scores[i] / max_cs
        else:
            cib_conf = 0.5

        combined = 0.4 * driver_conf + 0.6 * cib_conf
        confidences.append(round(combined, 3))
    return confidences


def build_scenarios_block(scenarios: list[Scenario]) -> str:
    parts = []
    for i, scenario in enumerate(scenarios):
        assumptions_text = "\n".join([f"  - {a.description}" for a in scenario.assumptions])
        perspective_line = f"\nPerspective: {scenario.perspective}" if scenario.perspective else ""
        tensions_line = f"\nKey tensions: {', '.join(scenario.key_tensions)}" if scenario.key_tensions else ""
        parts.append(
            f"### Scenario {i}: {scenario.title}\n"
            f"Type: {scenario.type.value}{perspective_line}{tensions_line}\n"
            f"Assumptions:\n{assumptions_text}\n"
            f"Narrative (excerpt): {scenario.narrative[:600]}"
        )
    return "\n\n".join(parts)


def _collect_source_chunks(scenarios: list[Scenario], collection) -> str:
    """Retrieve the actual source chunks that were used to generate the scenarios."""
    all_chunk_ids = []
    for s in scenarios:
        all_chunk_ids.extend(s.source_chunk_ids[:5])
    unique_ids = list(dict.fromkeys(all_chunk_ids))[:15]

    if not unique_ids or collection is None:
        return ""

    try:
        result = collection.get(ids=unique_ids, include=["documents", "metadatas"])
        parts = []
        for j in range(len(result["ids"])):
            cid = result["ids"][j]
            doc = result["documents"][j]
            meta = result["metadatas"][j]
            parts.append(f"[Chunk ID: {cid}] (Source: {meta.get('source_title', '?')})\n{doc}")
        return "\n\n---\n\n".join(parts)
    except Exception:
        log.warning("Failed to retrieve source chunks for evaluation, falling back to RAG query")
        return ""


def assess_scenarios(scenarios: list[Scenario], scenario_confidences: list[float], collection,
                     profile: DomainProfile | None = None) -> list[Assessment]:
    pkw = (profile or DomainProfile(domain="this technology domain")).prompt_kwargs()
    scenarios_block = build_scenarios_block(scenarios)

    rag_text = _collect_source_chunks(scenarios, collection)
    if not rag_text:
        combined_query = " ".join([s.title for s in scenarios])
        query_emb = embed([combined_query[:500]])[0]
        rag = collection.query(query_embeddings=[query_emb], n_results=5, include=["documents", "metadatas"])
        rag_text = "\n\n---\n\n".join([
            f"[Chunk ID: {rag['ids'][0][i]}] (Source: {rag['metadatas'][0][i]['source_title']})\n{rag['documents'][0][i]}"
            for i in range(len(rag["ids"][0]))
        ])

    prompt = SCENARIO_ASSESS.format(n=len(scenarios), scenarios_block=scenarios_block,
                                    rag_chunks=rag_text, **pkw)
    result = safe_chat_json(
        prompt,
        system=f"You are a strategic technology analyst at {pkw['actor']} evaluating future scenarios for {pkw['domain']}.",
        model=EVAL_MODEL,
    )

    assessments = []
    batch = result.get("assessments", [])
    for i, scenario in enumerate(scenarios):
        match = next((a for a in batch if a.get("scenario_index") == i), None)
        if match:
            assessment = Assessment(
                scenario_id=scenario.id,
                impact=match.get("impact", 5),
                probability=match.get("probability", 5),
                actionability=match.get("actionability", 5),
                time_horizon=match.get("time_horizon", 5),
                risk_severity=match.get("risk_severity", 5),
                confidence=scenario_confidences[i],
                reasoning=match.get("reasoning", ""),
                key_risks=match.get("key_risks", ""),
                early_signals=match.get("early_signals", ""),
                source_chunk_ids=match.get("source_chunk_ids_used", []),
            )
        else:
            assessment = Assessment(
                scenario_id=scenario.id, impact=5, probability=5,
                confidence=scenario_confidences[i],
                reasoning="No assessment returned",
            )
        assessments.append(assessment)
    return assessments


def assess_scenarios_batched(
    scenarios: list[Scenario],
    scenario_confidences: list[float],
    collection,
    batch_size: int = 8,
    profile: DomainProfile | None = None,
) -> list[Assessment]:
    """Assess scenarios in batches to stay within prompt length limits."""
    if len(scenarios) <= batch_size:
        return assess_scenarios(scenarios, scenario_confidences, collection, profile)

    all_assessments: list[Assessment] = []
    for start in range(0, len(scenarios), batch_size):
        end = min(start + batch_size, len(scenarios))
        batch_scenarios = scenarios[start:end]
        batch_confidences = scenario_confidences[start:end]
        batch_assessments = assess_scenarios(batch_scenarios, batch_confidences, collection, profile)
        all_assessments.extend(batch_assessments)
    return all_assessments


# ---------------------------------------------------------------------------
# AHP
# ---------------------------------------------------------------------------

def compute_ahp_weights(
    pairwise_matrix: list[list[float]],
    criteria: list[str] | None = None,
    cr_threshold: float = MCDA_CR_THRESHOLD,
) -> AHPWeights:
    criteria = criteria or MCDA_CRITERIA
    A = np.array(pairwise_matrix, dtype=float)
    n = A.shape[0]

    col_sums = A.sum(axis=0)
    normalized = A / col_sums
    weights = normalized.mean(axis=1)

    Aw = A @ weights
    lambdas = Aw / weights
    lambda_max = float(lambdas.mean())

    if n <= 2:
        cr = 0.0
    else:
        ci = (lambda_max - n) / (n - 1)
        ri = _RI.get(n, 1.49)
        cr = ci / ri if ri > 0 else 0.0

    is_consistent = cr < cr_threshold
    if not is_consistent:
        log.warning("AHP consistency ratio %.3f exceeds threshold %.2f", cr, cr_threshold)

    return AHPWeights(
        criteria=criteria,
        pairwise_matrix=pairwise_matrix,
        weights=weights.tolist(),
        consistency_ratio=round(cr, 4),
        is_consistent=is_consistent,
    )


# ---------------------------------------------------------------------------
# TOPSIS
# ---------------------------------------------------------------------------

def compute_topsis(
    decision_matrix: np.ndarray,
    weights: np.ndarray,
    benefit_criteria: list[bool] | None = None,
) -> list[float]:
    n_alt, n_crit = decision_matrix.shape
    if benefit_criteria is None:
        benefit_criteria = [True] * n_crit

    norms = np.sqrt((decision_matrix ** 2).sum(axis=0)) + 1e-10
    normalized = decision_matrix / norms

    weighted = normalized * weights

    ideal_best = np.where(benefit_criteria, weighted.max(axis=0), weighted.min(axis=0))
    ideal_worst = np.where(benefit_criteria, weighted.min(axis=0), weighted.max(axis=0))

    d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))

    closeness = d_worst / (d_best + d_worst + 1e-10)
    return closeness.tolist()


# ---------------------------------------------------------------------------
# MCDA orchestration
# ---------------------------------------------------------------------------

def run_mcda(
    assessments: list[Assessment],
    pairwise_matrix: list[list[float]] | None = None,
    criteria: list[str] | None = None,
) -> tuple[AHPWeights, list[MCDAResult]]:
    criteria = criteria or MCDA_CRITERIA
    pairwise_matrix = pairwise_matrix or MCDA_PAIRWISE_DEFAULT

    ahp = compute_ahp_weights(pairwise_matrix, criteria)
    weights = np.array(ahp.weights)

    dm = np.array([
        [getattr(a, c) for c in criteria]
        for a in assessments
    ])

    # risk_severity is a cost criterion: higher risk = worse, not better
    benefit_criteria = [True, True, True, True, False]
    closeness = compute_topsis(dm, weights, benefit_criteria=benefit_criteria)

    ranked_indices = sorted(range(len(closeness)), key=lambda i: closeness[i], reverse=True)
    rank_map = {idx: rank + 1 for rank, idx in enumerate(ranked_indices)}

    results = []
    for i, assessment in enumerate(assessments):
        scores = {c: getattr(assessment, c) for c in criteria}
        w_scores = {c: scores[c] * ahp.weights[j] for j, c in enumerate(criteria)}
        results.append(MCDAResult(
            scenario_id=assessment.scenario_id,
            criteria_scores=scores,
            weighted_scores={k: round(v, 4) for k, v in w_scores.items()},
            topsis_closeness=round(closeness[i], 4),
            rank=rank_map[i],
        ))

    return ahp, results


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------

def generate_traceability_report(scenarios: list[Scenario], assessments: list[Assessment],
                                  driver_by_id: dict, kb_state: dict,
                                  mcda_results: list[MCDAResult] | None = None) -> str:
    lines = ["TRACEABILITY REPORT"]
    source_by_id = kb_state["sources"]
    chunk_by_id = kb_state["chunks"]

    mcda_by_id = {r.scenario_id: r for r in mcda_results} if mcda_results else {}

    for scenario, assessment in zip(scenarios, assessments):
        mcda = mcda_by_id.get(scenario.id)
        rank_str = f" | MCDA Rank: #{mcda.rank} (closeness: {mcda.topsis_closeness:.3f})" if mcda else ""

        lines.append(f"\nSCENARIO: {scenario.title}")
        lines.append(f"Type: {scenario.type.value} | Impact: {assessment.impact} | Prob: {assessment.probability}{rank_str}")

        lines.append("  ASSUMPTIONS:")
        for a in scenario.assumptions:
            d = driver_by_id.get(a.driver_id)
            if d:
                lines.append(f"    {a.description} (origin: {d.origin.value}, confidence: {d.confidence.value})")

        lines.append("  SOURCE CHAIN:")
        seen = set()
        for chunk_id in scenario.source_chunk_ids:
            chunk = chunk_by_id.get(chunk_id)
            if chunk:
                src = source_by_id.get(chunk["source_id"])
                if src and src["id"] not in seen:
                    seen.add(src["id"])
                    lines.append(f"    {src['title']} [{src['type']}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run(
    scenario_state_path: str = "data/outputs/scenario_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    kb_state_path: str = "data/outputs/kb_state.json",
    output_path: str = "data/outputs/final_analysis.json",
    pairwise_matrix: list[list[float]] | None = None,
    consistency_scores: list[float] | None = None,
    profile: DomainProfile | None = None,
    collection="auto",
) -> dict:
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    if collection == "auto":
        collection = get_collection()

    with open(scenario_state_path) as f:
        scenarios = [Scenario(**s) for s in json.load(f)["scenarios"]]
    with open(merge_state_path) as f:
        drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]
    with open(kb_state_path) as f:
        kb_state = json.load(f)

    driver_by_id = {d.id: d for d in drivers}
    confidences = compute_scenario_confidences(scenarios, driver_by_id, consistency_scores)
    assessments = assess_scenarios_batched(scenarios, confidences, collection)

    ahp, mcda_results = run_mcda(assessments, pairwise_matrix=pairwise_matrix)

    state = {
        "assessments": [a.model_dump(mode="json") for a in assessments],
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
        "mcda": {
            "ahp_weights": ahp.model_dump(mode="json"),
            "rankings": [r.model_dump(mode="json") for r in mcda_results],
        },
    }
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    return state
