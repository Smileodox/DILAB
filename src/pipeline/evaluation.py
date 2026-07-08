"""Scenario Evaluation pipeline step.

Primary mode: pointwise, evidence-grounded auditing. Each scenario is scored in its own
bounded prompt against a per-scenario evidence budget (its own chunks + driver chunks +
"stress" RAG chunks), extracting facts BEFORE scoring to counter LLM positivity bias. The
grounded impact/probability/actionability/time_horizon/risk_severity scores then feed the
MCDA ranker (AHP + TOPSIS) unchanged, so the ranking is built on evidence-audited inputs.

A legacy comparative batch mode (``assess_scenarios`` / ``assess_scenarios_batched``) is
retained.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any

import numpy as np

from src.config import (
    CHROMA_PERSIST_DIR, EVAL_MODEL, MCDA_CRITERIA,
    MCDA_PAIRWISE_DEFAULT, MCDA_CR_THRESHOLD,
    MAX_EVIDENCE_CHUNKS_PER_SCENARIO, MAX_EVIDENCE_CHARS_PER_CHUNK,
    TARGET_SCENARIO_EVIDENCE_CHUNKS, TARGET_DRIVER_EVIDENCE_CHUNKS,
    TARGET_STRESS_EVIDENCE_CHUNKS, CIB_RELEVANCE_THRESHOLD,
    MAX_CIB_RELATIONSHIPS_PER_SCENARIO,
)
from src.llm import embed, safe_chat_json
from src.models.scenarios import Scenario
from src.models.evaluation import Assessment, AHPWeights, MCDAResult
from src.models.domain import DomainProfile
from src.models.drivers import TechDriver, DriverConfidence
from src.rag import get_collection, retrieve
from src.prompts.evaluation import (
    SCENARIO_ASSESS,
    SCENARIO_POINTWISE_EVIDENCE_ASSESS,
    SCENARIO_POINTWISE_SYSTEM,
)

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
# Pointwise, evidence-grounded auditor (primary evaluation mode)
# ---------------------------------------------------------------------------

def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _scenario_assumptions_text(scenario: Scenario) -> str:
    return "\n".join(f"- {a.description}" for a in scenario.assumptions)


def _string_or_join(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def _scenario_query(scenario: Scenario, driver_by_id: dict[str, TechDriver],
                    pkw: dict[str, str]) -> str:
    """Query for the 'stress' evidence chunks, framed by the docked domain (never hardwired)."""
    driver_names = []
    for a in scenario.assumptions:
        d = driver_by_id.get(a.driver_id)
        if d:
            driver_names.append(f"{d.name} {a.state}")
    return (f"{scenario.title} {scenario.perspective} {' '.join(driver_names[:6])} "
            f"{pkw['domain']} {pkw['horizon']}")


def format_labeled_evidence(chunks: list[dict[str, str]]) -> tuple[str, dict[str, str]]:
    """Format the fixed-size pointwise evidence with [E#] labels; return label -> chunk_id map."""
    parts: list[str] = []
    label_map: dict[str, str] = {}
    for i, chunk in enumerate(chunks[:MAX_EVIDENCE_CHUNKS_PER_SCENARIO], start=1):
        label = f"E{i}"
        label_map[label] = chunk["chunk_id"]
        parts.append(
            f"[{label}] Chunk ID: {chunk['chunk_id']} | Source: {chunk['source_title']}\n"
            f"{chunk['content'][:MAX_EVIDENCE_CHARS_PER_CHUNK]}"
        )
    return "\n\n".join(parts), label_map


def _labels_to_chunk_ids(labels: list[str], label_map: dict[str, str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for label in labels or []:
        chunk_id = label_map.get(str(label).strip())
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            ids.append(chunk_id)
    return ids


def build_scenario_evidence(
    scenarios: list[Scenario],
    driver_by_id: dict[str, TechDriver],
    collection,
    pkw: dict[str, str],
    max_chunks: int = MAX_EVIDENCE_CHUNKS_PER_SCENARIO,
) -> dict[int, list[dict[str, str]]]:
    """Balanced per-scenario evidence budget: scenario chunks + driver chunks + stress RAG chunks.

    A fixed chunk/char cap per scenario holds evidence length constant across scenarios so a
    longer narrative cannot bias the score.
    """
    # Collect the linked (scenario + driver) chunk ids up front for one batched .get().
    linked_ids_by_idx: dict[int, list[str]] = {}
    all_ids: list[str] = []
    for i, scenario in enumerate(scenarios):
        scenario_ids = _ordered_unique(list(scenario.source_chunk_ids))
        driver_ids: list[str] = []
        for a in scenario.assumptions:
            d = driver_by_id.get(a.driver_id)
            if d:
                driver_ids.extend(d.source_chunk_ids)
        ids = _ordered_unique(scenario_ids + driver_ids)
        linked_ids_by_idx[i] = ids
        all_ids.extend(ids)

    chunk_by_id: dict[str, dict[str, str]] = {}
    unique_ids = _ordered_unique(all_ids)
    if unique_ids:
        try:
            fetched = collection.get(ids=unique_ids, include=["documents", "metadatas"])
            for chunk_id, doc, meta in zip(
                fetched.get("ids", []),
                fetched.get("documents", []),
                fetched.get("metadatas", []),
            ):
                chunk_by_id[chunk_id] = {
                    "chunk_id": chunk_id,
                    "content": doc or "",
                    "source_title": (meta or {}).get("source_title", "unknown source"),
                }
        except Exception:
            log.warning("Failed to fetch linked evidence chunks; falling back to stress RAG only")
            chunk_by_id = {}

    evidence_by_idx: dict[int, list[dict[str, str]]] = {}
    for i, scenario in enumerate(scenarios):
        scenario_ids = _ordered_unique(list(scenario.source_chunk_ids))
        driver_ids: list[str] = []
        for a in scenario.assumptions:
            d = driver_by_id.get(a.driver_id)
            if d:
                driver_ids.extend(d.source_chunk_ids)
        driver_ids = _ordered_unique(driver_ids)

        scenario_chunks = [chunk_by_id[cid] for cid in scenario_ids if cid in chunk_by_id][
            :TARGET_SCENARIO_EVIDENCE_CHUNKS
        ]
        picked = {c["chunk_id"] for c in scenario_chunks}
        driver_chunks = [
            chunk_by_id[cid] for cid in driver_ids
            if cid in chunk_by_id and cid not in picked
        ][:TARGET_DRIVER_EVIDENCE_CHUNKS]

        chunks = scenario_chunks + driver_chunks
        existing = {c["chunk_id"] for c in chunks}

        # "Stress" chunks: semantically-retrieved evidence the scenario did NOT itself cite.
        stress_query = _scenario_query(scenario, driver_by_id, pkw)[:500]
        try:
            stress_pool = retrieve(
                collection, stress_query,
                n=max(max_chunks, TARGET_STRESS_EVIDENCE_CHUNKS * 4),
            )
        except Exception:
            log.warning("Stress RAG retrieval failed for scenario %s", scenario.id)
            stress_pool = []
        stress_added = 0
        for c in stress_pool:
            if c["chunk_id"] in existing:
                continue
            chunks.append({
                "chunk_id": c["chunk_id"],
                "content": c.get("content") or "",
                "source_title": c.get("source_title", "unknown source"),
            })
            existing.add(c["chunk_id"])
            stress_added += 1
            if stress_added >= TARGET_STRESS_EVIDENCE_CHUNKS:
                break

        # Top up from any remaining linked chunks if still under budget.
        if len(chunks) < max_chunks:
            fallback = [
                chunk_by_id[cid] for cid in linked_ids_by_idx[i]
                if cid in chunk_by_id and cid not in existing
            ]
            chunks.extend(fallback[: max_chunks - len(chunks)])

        evidence_by_idx[i] = chunks[:max_chunks]

    return evidence_by_idx


def load_cib_state(cib_state_path: str | None) -> dict[str, Any]:
    if not cib_state_path:
        return {}
    try:
        with open(cib_state_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def build_cib_context_by_scenario(
    scenarios: list[Scenario],
    driver_by_id: dict[str, TechDriver],
    cib_state: dict[str, Any],
) -> dict[int, str]:
    """Surface the strongest CIB promoting/inhibiting relations among each scenario's drivers."""
    matrix = cib_state.get("matrix", [])
    driver_ids = cib_state.get("driver_ids", [])
    id_to_idx = {driver_id: i for i, driver_id in enumerate(driver_ids)}
    context_by_idx: dict[int, str] = {}

    for scenario_idx, scenario in enumerate(scenarios):
        scenario_driver_ids = [a.driver_id for a in scenario.assumptions]
        relationships: list[tuple[int, str]] = []
        for source_id in scenario_driver_ids:
            source_idx = id_to_idx.get(source_id)
            if source_idx is None or source_idx >= len(matrix):
                continue
            for target_id in scenario_driver_ids:
                if source_id == target_id:
                    continue
                target_idx = id_to_idx.get(target_id)
                if target_idx is None or target_idx >= len(matrix[source_idx]):
                    continue
                score = int(matrix[source_idx][target_idx])
                if abs(score) < CIB_RELEVANCE_THRESHOLD:
                    continue
                source = driver_by_id.get(source_id)
                target = driver_by_id.get(target_id)
                if not source or not target:
                    continue
                effect = "promotes" if score > 0 else "inhibits"
                relationships.append(
                    (abs(score), f"- {source.name} {effect} {target.name} (CIB score: {score:+d})")
                )
        relationships.sort(key=lambda item: item[0], reverse=True)
        selected = [text for _, text in relationships[:MAX_CIB_RELATIONSHIPS_PER_SCENARIO]]
        context_by_idx[scenario_idx] = (
            "\n".join(selected) if selected
            else (f"No strong CIB relationships (absolute score >= {CIB_RELEVANCE_THRESHOLD}) "
                  "among this scenario's drivers.")
        )
    return context_by_idx


def _score_or_default(value, default: float, field: str, scenario_id: str) -> float:
    """Coerce a judge score to float; fall back (with a warning) if missing/non-numeric.

    A missing criterion degrades gracefully: a constant column is non-discriminating in TOPSIS,
    so a partial judge failure does not crash the ranking.
    """
    if value is None or value == "":
        log.warning("Pointwise auditor omitted %s for scenario %s; using default %.1f",
                    field, scenario_id, default)
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        log.warning("Pointwise auditor returned non-numeric %s=%r for scenario %s; using default %.1f",
                    field, value, scenario_id, default)
        return default


def _assessment_from_judge(
    result: dict[str, Any],
    scenario: Scenario,
    evidence_chunks: list[dict[str, str]],
    label_map: dict[str, str],
    confidence: float = 0.5,
) -> Assessment:
    """Map the auditor's JSON verdict onto an Assessment (pure — no LLM/IO, unit-testable)."""
    impact_eval = result.get("impact_evaluation", {})
    probability_eval = result.get("probability_evaluation", {})
    risks = result.get("risks", {})
    signals = result.get("signals_and_actionability", {})
    cib_consistency = result.get("cib_consistency", {})
    rag_facts = result.get("rag_fact_extraction", {})

    source_labels = result.get("source_evidence_labels_used", [])
    source_chunk_ids = _labels_to_chunk_ids(source_labels, label_map)
    if not source_chunk_ids:
        source_chunk_ids = [c["chunk_id"] for c in evidence_chunks]

    grounding_strength = result.get("grounding_strength", "")
    grounding_reason = result.get("grounding_reason", "")
    reasoning = (
        f"Grounding: {grounding_strength}. {grounding_reason}\n"
        f"Supporting evidence: {_string_or_join(rag_facts.get('supporting_evidence'))}\n"
        f"Limiting evidence: {_string_or_join(rag_facts.get('contradictory_or_limiting_evidence'))}\n"
        f"Inference from evidence: {_string_or_join(rag_facts.get('inference_from_evidence'))}\n"
        f"Unsupported claims: {_string_or_join(rag_facts.get('unsupported_claims'))}\n"
        f"CIB consistency: {cib_consistency.get('reason', '')}\n"
        f"Impact: {impact_eval.get('score_boundary_justification', '')}\n"
        f"Probability: {probability_eval.get('score_boundary_justification', '')}"
    )

    return Assessment(
        scenario_id=scenario.id,
        impact=_score_or_default(impact_eval.get("final_impact_score"), 5.0, "impact", scenario.id),
        probability=_score_or_default(
            probability_eval.get("final_probability_score"), 5.0, "probability", scenario.id),
        actionability=_score_or_default(
            signals.get("actionability_score"), 5.0, "actionability", scenario.id),
        time_horizon=_score_or_default(
            signals.get("time_horizon_score"), 5.0, "time_horizon", scenario.id),
        risk_severity=_score_or_default(
            risks.get("severity_score"), 5.0, "risk_severity", scenario.id),
        confidence=confidence,
        reasoning=reasoning,
        key_risks=_string_or_join(risks.get("analysis")),
        early_signals=_string_or_join(signals.get("observable_signals")),
        recommended_actions=_string_or_join(signals.get("recommended_actions")),
        grounding_strength=grounding_strength,
        grounding_reason=grounding_reason,
        cib_consistency_strength=cib_consistency.get("strength", ""),
        cib_consistency_reason=cib_consistency.get("reason", ""),
        source_chunk_ids=source_chunk_ids,
    )


def assess_single_scenario_pointwise(
    scenario: Scenario,
    evidence_chunks: list[dict[str, str]],
    cib_context: str,
    pkw: dict[str, str],
    confidence: float = 0.5,
    model: str = EVAL_MODEL,
) -> tuple[Assessment, dict[str, Any]]:
    """Score one scenario against its own labeled evidence, extracting facts before scoring."""
    evidence_block, label_map = format_labeled_evidence(evidence_chunks)
    prompt = SCENARIO_POINTWISE_EVIDENCE_ASSESS.format(
        scenario_title=scenario.title,
        scenario_type=scenario.type.value,
        scenario_perspective=scenario.perspective,
        scenario_assumptions=_scenario_assumptions_text(scenario),
        scenario_narrative=scenario.narrative[:3000],
        evidence_block=evidence_block or "No scenario-specific source chunks available.",
        cib_context=cib_context,
        **pkw,
    )
    result = safe_chat_json(prompt, system=SCENARIO_POINTWISE_SYSTEM, model=model)
    assessment = _assessment_from_judge(result, scenario, evidence_chunks, label_map, confidence)
    audit = {
        "scenario_id": scenario.id,
        "evidence_label_to_chunk_id": label_map,
        "cib_context": cib_context,
        "raw_judge_output": result,
    }
    return assessment, audit


def assess_scenarios_pointwise(
    scenarios: list[Scenario],
    drivers: list[TechDriver],
    collection,
    profile: DomainProfile | None = None,
    cib_state: dict[str, Any] | None = None,
    scenario_confidences: list[float] | None = None,
) -> tuple[list[Assessment], dict[str, Any]]:
    """Score every scenario with the evidence-grounded auditor (one LLM call per scenario)."""
    pkw = (profile or DomainProfile(domain="this technology domain")).prompt_kwargs()
    driver_by_id = {d.id: d for d in drivers}
    if scenario_confidences is None:
        scenario_confidences = compute_scenario_confidences(scenarios, driver_by_id)

    evidence_by_idx = build_scenario_evidence(scenarios, driver_by_id, collection, pkw)
    cib_context_by_idx = build_cib_context_by_scenario(scenarios, driver_by_id, cib_state or {})

    assessments: list[Assessment] = []
    audits: list[dict[str, Any]] = []
    for i, scenario in enumerate(scenarios):
        confidence = scenario_confidences[i] if i < len(scenario_confidences) else 0.5
        assessment, audit = assess_single_scenario_pointwise(
            scenario,
            evidence_by_idx.get(i, []),
            cib_context_by_idx.get(i, "No CIB context available."),
            pkw,
            confidence=confidence,
        )
        assessments.append(assessment)
        audits.append(audit)

    metadata = {
        "evaluation_mode": "pointwise_evidence_grounded",
        "comparative_scoring": False,
        "position_bias_mitigation": "not_required_one_scenario_per_call",
        "attribute_interference_mitigation": "ordered_fact_extraction_before_scoring",
        "total_llm_calls": len(scenarios),
        "evidence_context": {
            "strategy": "scenario_source_chunks_plus_driver_chunks_with_stress_rag",
            "max_chunks_per_scenario": MAX_EVIDENCE_CHUNKS_PER_SCENARIO,
            "max_chars_per_chunk": MAX_EVIDENCE_CHARS_PER_CHUNK,
            "target_composition": {
                "scenario_generation_chunks": TARGET_SCENARIO_EVIDENCE_CHUNKS,
                "driver_linked_chunks": TARGET_DRIVER_EVIDENCE_CHUNKS,
                "stress_rag_chunks": TARGET_STRESS_EVIDENCE_CHUNKS,
            },
            "length_bias_control": "same chunk and character cap for each scenario",
        },
        "cib_context": {
            "strategy": "existing_cib_matrix_lookup_for_scenario_drivers",
            "relevance_threshold_abs_score": CIB_RELEVANCE_THRESHOLD,
            "max_relationships_per_scenario": MAX_CIB_RELATIONSHIPS_PER_SCENARIO,
        },
        "domain_context": {
            "domain": pkw["domain"],
            "horizon": pkw["horizon"],
            "actor": pkw["actor"],
        },
        "evidence_audit_by_scenario": audits,
        "post_run_checks_recommended": [
            "plot impact and probability score distributions",
            "cross-tabulate grounding_strength against impact/probability/confidence",
            "flag if unsupported_claims is 'None' for nearly every scenario",
        ],
    }
    return assessments, metadata


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
    cib_state_path: str | None = None,
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
    with open(kb_state_path):
        pass  # loaded/validated; traceability chain is resolved via source_chunk_ids downstream

    driver_by_id = {d.id: d for d in drivers}
    confidences = compute_scenario_confidences(scenarios, driver_by_id, consistency_scores)
    cib_state = load_cib_state(cib_state_path)

    # Evidence-grounded auditor produces the numeric MCDA criteria (grounded, not positivity-biased),
    # which then feed AHP+TOPSIS unchanged. Grounding/audit fields ride along on each Assessment.
    assessments, eval_meta = assess_scenarios_pointwise(
        scenarios, drivers, collection,
        profile=profile, cib_state=cib_state, scenario_confidences=confidences,
    )

    ahp, mcda_results = run_mcda(assessments, pairwise_matrix=pairwise_matrix)

    state = {
        "assessments": [a.model_dump(mode="json") for a in assessments],
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
        "mcda": {
            "ahp_weights": ahp.model_dump(mode="json"),
            "rankings": [r.model_dump(mode="json") for r in mcda_results],
        },
        "evaluation_metadata": eval_meta,
    }
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    return state
