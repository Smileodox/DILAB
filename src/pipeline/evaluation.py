"""Scenario Evaluation pipeline step.

Input: data/outputs/scenario_state.json + merge_state.json + kb_state.json (or fixtures)
Output: data/outputs/final_analysis.json

Main mode: pointwise evidence-grounded evaluation. Each scenario is evaluated in one bounded
prompt against its own labeled evidence set, with fact extraction before scoring.

Legacy mode: batch comparative evaluation with separated dimensions and numeric position-bias
mitigation is retained as assess_scenarios_batch_comparative().
"""

from __future__ import annotations

import json
from typing import Any

import chromadb
import numpy as np

from src.config import CHROMA_PERSIST_DIR
from src.llm import embed, safe_chat_json
from src.models.drivers import TechDriver
from src.models.evaluation import Assessment
from src.models.scenarios import Scenario
from src.prompts.evaluation import (
    SCENARIO_ASSESS,
    SCENARIO_ASSESS_SYSTEM,
    SCENARIO_IMPACT_ASSESS,
    SCENARIO_PROBABILITY_ASSESS,
    SCENARIO_POINTWISE_EVIDENCE_ASSESS,
    SCENARIO_POINTWISE_SYSTEM,
    SCENARIO_RISK_ASSESS,
    SCENARIO_SIGNALS_ASSESS,
)

CONF_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}
DEFAULT_BATCH_SIZE = 8
MAX_EVIDENCE_CHUNKS_PER_SCENARIO = 6
MAX_EVIDENCE_CHARS_PER_CHUNK = 700
TARGET_SCENARIO_EVIDENCE_CHUNKS = 2
TARGET_DRIVER_EVIDENCE_CHUNKS = 2
TARGET_STRESS_EVIDENCE_CHUNKS = 2
MAX_CIB_RELATIONSHIPS_PER_SCENARIO = 6
CIB_RELEVANCE_THRESHOLD = 2
DOMAIN_NAME = "regulatory frequency monitoring"
TARGET_YEAR = "2035"
ORG_CONTEXT = "Rohde & Schwarz product and R&D strategy"


def format_scenario_block(ordered_scenarios: list[tuple[int, Scenario]]) -> str:
    """Build prompt block; presentation index 0..n-1 maps via ordered_scenarios[i][0]."""
    parts: list[str] = []
    for presentation_idx, (_, scenario) in enumerate(ordered_scenarios):
        assumptions_text = "\n".join(f"  - {a.description}" for a in scenario.assumptions)
        perspective_line = f"\nPerspective: {scenario.perspective}" if scenario.perspective else ""
        tensions_line = (
            f"\nKey tensions: {', '.join(scenario.key_tensions)}" if scenario.key_tensions else ""
        )
        parts.append(
            f"### Scenario {presentation_idx}: {scenario.title}\n"
            f"Type: {scenario.type.value}{perspective_line}{tensions_line}\n"
            f"Assumptions:\n{assumptions_text}\n"
            f"Narrative (excerpt): {scenario.narrative[:600]}"
        )
    return "\n\n".join(parts)


def format_evidence_block(
    ordered_scenarios: list[tuple[int, Scenario]],
    evidence_by_original_idx: dict[int, list[dict[str, str]]],
) -> str:
    """Format compact scenario-specific evidence using presentation indices."""
    parts: list[str] = []
    for presentation_idx, (original_idx, scenario) in enumerate(ordered_scenarios):
        chunks = evidence_by_original_idx.get(original_idx, [])
        chunk_text = "\n\n".join(
            f"[Chunk ID: {chunk['chunk_id']}] (Source: {chunk['source_title']})\n"
            f"{chunk['content'][:MAX_EVIDENCE_CHARS_PER_CHUNK]}"
            for chunk in chunks
        )
        if not chunk_text:
            chunk_text = "No scenario-specific source chunks available."
        parts.append(f"### Evidence for Scenario {presentation_idx}: {scenario.title}\n{chunk_text}")
    return "\n\n---\n\n".join(parts)


def format_labeled_evidence(
    chunks: list[dict[str, str]],
) -> tuple[str, dict[str, str]]:
    """Format fixed-size pointwise evidence labels and return label -> chunk_id mapping."""
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


def presentation_to_original(ordered_scenarios: list[tuple[int, Scenario]]) -> list[int]:
    return [original_idx for original_idx, _ in ordered_scenarios]


def compute_scenario_confidences(
    scenarios: list[Scenario],
    driver_by_id: dict[str, TechDriver],
) -> list[float]:
    confidences: list[float] = []
    for scenario in scenarios:
        driver_confs = []
        for assumption in scenario.assumptions:
            driver = driver_by_id.get(assumption.driver_id)
            if driver:
                driver_confs.append(CONF_MAP.get(driver.confidence.value, 0.5))
        confidences.append(round(float(np.mean(driver_confs)), 2) if driver_confs else 0.5)
    return confidences


def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _scenario_query(scenario: Scenario, driver_by_id: dict[str, TechDriver]) -> str:
    driver_names = []
    for assumption in scenario.assumptions:
        driver = driver_by_id.get(assumption.driver_id)
        if driver:
            driver_names.append(f"{driver.name} {assumption.state}")
    return f"{scenario.title} {scenario.perspective} {' '.join(driver_names[:6])} spectrum monitoring 2035"


def build_scenario_evidence(
    scenarios: list[Scenario],
    driver_by_id: dict[str, TechDriver],
    collection: chromadb.Collection,
    max_chunks: int = MAX_EVIDENCE_CHUNKS_PER_SCENARIO,
) -> dict[int, list[dict[str, str]]]:
    """Use a balanced evidence budget: scenario chunks, driver chunks, and stress RAG chunks."""
    linked_ids_by_idx: dict[int, list[str]] = {}
    all_ids: list[str] = []

    for i, scenario in enumerate(scenarios):
        scenario_ids = _ordered_unique(list(scenario.source_chunk_ids))
        driver_ids: list[str] = []
        for assumption in scenario.assumptions:
            driver = driver_by_id.get(assumption.driver_id)
            if driver:
                driver_ids.extend(driver.source_chunk_ids)
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
            chunk_by_id = {}

    evidence_by_idx: dict[int, list[dict[str, str]]] = {}
    for i, scenario in enumerate(scenarios):
        scenario_ids = _ordered_unique(list(scenario.source_chunk_ids))
        driver_ids: list[str] = []
        for assumption in scenario.assumptions:
            driver = driver_by_id.get(assumption.driver_id)
            if driver:
                driver_ids.extend(driver.source_chunk_ids)
        driver_ids = _ordered_unique(driver_ids)

        scenario_chunks = [
            chunk_by_id[cid]
            for cid in scenario_ids
            if cid in chunk_by_id
        ][:TARGET_SCENARIO_EVIDENCE_CHUNKS]
        driver_chunks = [
            chunk_by_id[cid]
            for cid in driver_ids
            if cid in chunk_by_id and cid not in {c["chunk_id"] for c in scenario_chunks}
        ][:TARGET_DRIVER_EVIDENCE_CHUNKS]

        chunks = scenario_chunks + driver_chunks
        existing = {c["chunk_id"] for c in chunks}

        query_emb = embed([_scenario_query(scenario, driver_by_id)[:500]])[0]
        rag = collection.query(
            query_embeddings=[query_emb],
            n_results=max(max_chunks, TARGET_STRESS_EVIDENCE_CHUNKS * 4),
            include=["documents", "metadatas"],
        )
        stress_chunks: list[dict[str, str]] = []
        for j in range(len(rag["ids"][0])):
            chunk_id = rag["ids"][0][j]
            if chunk_id in existing:
                continue
            stress_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "content": rag["documents"][0][j] or "",
                    "source_title": rag["metadatas"][0][j].get("source_title", "unknown source"),
                }
            )
            existing.add(chunk_id)
            if len(stress_chunks) >= TARGET_STRESS_EVIDENCE_CHUNKS:
                break

        chunks.extend(stress_chunks)

        if len(chunks) < max_chunks:
            fallback = [
                chunk_by_id[cid]
                for cid in linked_ids_by_idx[i]
                if cid in chunk_by_id and cid not in {c["chunk_id"] for c in chunks}
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
                    (
                        abs(score),
                        f"- {source.name} {effect} {target.name} (CIB score: {score:+d})",
                    )
                )

        relationships.sort(key=lambda item: item[0], reverse=True)
        selected = [text for _, text in relationships[:MAX_CIB_RELATIONSHIPS_PER_SCENARIO]]
        context_by_idx[scenario_idx] = (
            "\n".join(selected)
            if selected
            else "No strong CIB relationships (absolute score >= 2) among this scenario's drivers."
        )

    return context_by_idx


def _parse_batch_by_original_index(
    result: dict[str, Any],
    index_map: list[int],
) -> dict[int, dict[str, Any]]:
    """Map presentation-order scenario_index values back to original scenario indices."""
    by_original: dict[int, dict[str, Any]] = {}
    for item in result.get("assessments", []):
        presentation_idx = item.get("scenario_index")
        if presentation_idx is None or not (0 <= presentation_idx < len(index_map)):
            continue
        by_original[index_map[presentation_idx]] = item
    return by_original


def run_assessment_pass(
    scenarios: list[Scenario],
    evidence_by_original_idx: dict[int, list[dict[str, str]]],
    presentation_order: list[int],
    prompt_template: str = SCENARIO_ASSESS,
) -> dict[int, dict[str, Any]]:
    ordered = [(idx, scenarios[idx]) for idx in presentation_order]
    prompt = prompt_template.format(
        n=len(ordered),
        scenarios_block=format_scenario_block(ordered),
        rag_chunks=format_evidence_block(ordered, evidence_by_original_idx),
    )
    result = safe_chat_json(prompt, system=SCENARIO_ASSESS_SYSTEM)
    return _parse_batch_by_original_index(result, presentation_to_original(ordered))


def _avg_score(a: float | None, b: float | None, default: float = 5.0) -> float:
    values = [v for v in (a, b) if v is not None]
    if not values:
        return default
    return round(sum(float(v) for v in values) / len(values), 2)


def merge_position_bias_passes(
    forward: dict[int, dict[str, Any]],
    reversed_pass: dict[int, dict[str, Any]],
    n: int,
) -> list[dict[str, Any]]:
    """Average impact/probability across forward and reversed presentation orders."""
    merged: list[dict[str, Any]] = []
    for original_idx in range(n):
        fwd = forward.get(original_idx, {})
        rev = reversed_pass.get(original_idx, {})
        merged.append(
            {
                "impact": _avg_score(fwd.get("impact"), rev.get("impact")),
                "probability": _avg_score(fwd.get("probability"), rev.get("probability")),
                "reasoning": fwd.get("reasoning") or rev.get("reasoning") or "No assessment returned",
                "key_risks": fwd.get("key_risks") or rev.get("key_risks", ""),
                "early_signals": fwd.get("early_signals") or rev.get("early_signals", ""),
                "actionability": fwd.get("actionability") or rev.get("actionability", ""),
                "source_chunk_ids_used": fwd.get("source_chunk_ids_used")
                or rev.get("source_chunk_ids_used", []),
                "impact_by_pass": [fwd.get("impact"), rev.get("impact")],
                "probability_by_pass": [fwd.get("probability"), rev.get("probability")],
            }
        )
    return merged


def _merge_source_ids(*items: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in items:
        for chunk_id in item.get("source_chunk_ids_used", []) or []:
            if chunk_id not in seen:
                seen.add(chunk_id)
                merged.append(chunk_id)
    return merged


def _run_dual_order_dimension(
    scenarios: list[Scenario],
    evidence_by_original_idx: dict[int, list[dict[str, str]]],
    scenario_indices: list[int],
    prompt_template: str,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    forward = run_assessment_pass(
        scenarios,
        evidence_by_original_idx,
        scenario_indices,
        prompt_template,
    )
    reversed_pass = run_assessment_pass(
        scenarios,
        evidence_by_original_idx,
        list(reversed(scenario_indices)),
        prompt_template,
    )
    return forward, reversed_pass


def _pick_text(
    forward: dict[str, Any],
    reversed_pass: dict[str, Any],
    key: str,
    default: str = "",
) -> str:
    return forward.get(key) or reversed_pass.get(key) or default


def _scenario_assumptions_text(scenario: Scenario) -> str:
    return "\n".join(f"- {a.description}" for a in scenario.assumptions)


def _labels_to_chunk_ids(labels: list[str], label_map: dict[str, str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for label in labels or []:
        chunk_id = label_map.get(str(label).strip())
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            ids.append(chunk_id)
    return ids


def _string_or_join(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def assess_single_scenario_pointwise(
    scenario: Scenario,
    evidence_chunks: list[dict[str, str]],
    cib_context: str = "No CIB context available.",
    domain_name: str = DOMAIN_NAME,
    target_year: str = TARGET_YEAR,
    org_context: str = ORG_CONTEXT,
) -> tuple[Assessment, dict[str, Any]]:
    evidence_block, label_map = format_labeled_evidence(evidence_chunks)
    prompt = SCENARIO_POINTWISE_EVIDENCE_ASSESS.format(
        domain_name=domain_name,
        target_year=target_year,
        org_context=org_context,
        scenario_title=scenario.title,
        scenario_type=scenario.type.value,
        scenario_perspective=scenario.perspective,
        scenario_assumptions=_scenario_assumptions_text(scenario),
        scenario_narrative=scenario.narrative[:3000],
        evidence_block=evidence_block,
        cib_context=cib_context,
    )
    result = safe_chat_json(prompt, system=SCENARIO_POINTWISE_SYSTEM)

    impact_eval = result.get("impact_evaluation", {})
    probability_eval = result.get("probability_evaluation", {})
    risks = result.get("risks", {})
    signals = result.get("signals_and_actionability", {})
    cib_consistency = result.get("cib_consistency", {})
    rag_facts = result.get("rag_fact_extraction", {})
    source_labels = result.get("source_evidence_labels_used", [])
    source_chunk_ids = _labels_to_chunk_ids(source_labels, label_map)
    if not source_chunk_ids:
        source_chunk_ids = [chunk["chunk_id"] for chunk in evidence_chunks]

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

    assessment = Assessment(
        scenario_id=scenario.id,
        impact=float(impact_eval.get("final_impact_score", 5)),
        probability=float(probability_eval.get("final_probability_score", 5)),
        confidence=0.5,
        reasoning=reasoning,
        key_risks=risks.get("analysis", ""),
        early_signals=signals.get("observable_signals", ""),
        actionability=signals.get("recommended_actions", ""),
        grounding_strength=grounding_strength,
        grounding_reason=grounding_reason,
        cib_consistency_strength=cib_consistency.get("strength", ""),
        cib_consistency_reason=cib_consistency.get("reason", ""),
        source_chunk_ids=source_chunk_ids,
    )

    audit = {
        "scenario_id": scenario.id,
        "evidence_label_to_chunk_id": label_map,
        "cib_context": cib_context,
        "raw_judge_output": result,
    }
    return assessment, audit


def assess_scenarios(
    scenarios: list[Scenario],
    drivers: list[TechDriver],
    collection: chromadb.Collection | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cib_state: dict[str, Any] | None = None,
) -> tuple[list[Assessment], dict[str, Any]]:
    """Evaluate scenarios with dual-order averaging to mitigate position bias."""
    if collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_collection("knowledge_base")

    driver_by_id = {d.id: d for d in drivers}
    confidences = compute_scenario_confidences(scenarios, driver_by_id)
    evidence_by_original_idx = build_scenario_evidence(scenarios, driver_by_id, collection)
    cib_context_by_idx = build_cib_context_by_scenario(
        scenarios,
        driver_by_id,
        cib_state or {},
    )

    assessments: list[Assessment] = []
    audits: list[dict[str, Any]] = []
    for i, scenario in enumerate(scenarios):
        assessment, audit = assess_single_scenario_pointwise(
            scenario,
            evidence_by_original_idx.get(i, []),
            cib_context_by_idx.get(i, "No CIB context available."),
        )
        assessment.confidence = confidences[i]
        assessments.append(assessment)
        audits.append(audit)

    metadata = {
        "evaluation_mode": "pointwise_evidence_grounded",
        "comparative_scoring": False,
        "position_bias_mitigation": "not_required_one_scenario_per_call",
        "attribute_interference_mitigation": "ordered_fact_extraction_before_scoring",
        "total_llm_calls": len(scenarios),
        "evidence_context": {
            "strategy": "scenario_source_chunks_plus_driver_chunks_with_rag_fallback",
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
            "domain_name": DOMAIN_NAME,
            "target_year": TARGET_YEAR,
            "org_context": ORG_CONTEXT,
        },
        "evidence_audit_by_scenario": audits,
        "post_run_checks_recommended": [
            "plot impact and probability score distributions",
            "cross-tabulate grounding_strength against impact/probability/confidence",
            "flag if unsupported_claims is 'None' for nearly every scenario",
        ],
    }
    return assessments, metadata


def assess_scenarios_batch_comparative(
    scenarios: list[Scenario],
    drivers: list[TechDriver],
    collection: chromadb.Collection | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[list[Assessment], dict[str, Any]]:
    """Legacy comparative mode with separated dimensions and numeric position-bias mitigation."""
    if collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_collection("knowledge_base")

    driver_by_id = {d.id: d for d in drivers}
    confidences = compute_scenario_confidences(scenarios, driver_by_id)
    evidence_by_original_idx = build_scenario_evidence(scenarios, driver_by_id, collection)

    n = len(scenarios)
    batch_size = max(1, batch_size)
    forward_order = list(range(n))
    batches = [forward_order[i : i + batch_size] for i in range(0, n, batch_size)]

    impact_forward: dict[int, dict[str, Any]] = {}
    impact_reversed: dict[int, dict[str, Any]] = {}
    probability_forward: dict[int, dict[str, Any]] = {}
    probability_reversed: dict[int, dict[str, Any]] = {}
    risk_forward: dict[int, dict[str, Any]] = {}
    signals_forward: dict[int, dict[str, Any]] = {}

    for batch_indices in batches:
        batch_impact_forward, batch_impact_reversed = _run_dual_order_dimension(
            scenarios,
            evidence_by_original_idx,
            batch_indices,
            SCENARIO_IMPACT_ASSESS,
        )
        impact_forward.update(batch_impact_forward)
        impact_reversed.update(batch_impact_reversed)

        batch_probability_forward, batch_probability_reversed = _run_dual_order_dimension(
            scenarios,
            evidence_by_original_idx,
            batch_indices,
            SCENARIO_PROBABILITY_ASSESS,
        )
        probability_forward.update(batch_probability_forward)
        probability_reversed.update(batch_probability_reversed)

        risk_forward.update(
            run_assessment_pass(
                scenarios,
                evidence_by_original_idx,
                batch_indices,
                SCENARIO_RISK_ASSESS,
            )
        )
        signals_forward.update(
            run_assessment_pass(
                scenarios,
                evidence_by_original_idx,
                batch_indices,
                SCENARIO_SIGNALS_ASSESS,
            )
        )

    assessments: list[Assessment] = []
    score_variance: list[dict[str, Any]] = []
    for i, scenario in enumerate(scenarios):
        impact_fwd = impact_forward.get(i, {})
        impact_rev = impact_reversed.get(i, {})
        probability_fwd = probability_forward.get(i, {})
        probability_rev = probability_reversed.get(i, {})
        risk_fwd = risk_forward.get(i, {})
        risk_rev: dict[str, Any] = {}
        signals_fwd = signals_forward.get(i, {})
        signals_rev: dict[str, Any] = {}

        impact = _avg_score(impact_fwd.get("impact"), impact_rev.get("impact"))
        probability = _avg_score(
            probability_fwd.get("probability"),
            probability_rev.get("probability"),
        )
        impact_reasoning = _pick_text(
            impact_fwd,
            impact_rev,
            "impact_reasoning",
            "No impact assessment returned",
        )
        probability_reasoning = _pick_text(
            probability_fwd,
            probability_rev,
            "probability_reasoning",
            "No probability assessment returned",
        )
        key_risks = _pick_text(risk_fwd, risk_rev, "key_risks")
        risk_reasoning = _pick_text(risk_fwd, risk_rev, "risk_reasoning")
        early_signals = _pick_text(signals_fwd, signals_rev, "early_signals")
        actionability = _pick_text(signals_fwd, signals_rev, "actionability")
        signals_reasoning = _pick_text(signals_fwd, signals_rev, "signals_reasoning")
        source_ids = _merge_source_ids(
            impact_fwd,
            impact_rev,
            probability_fwd,
            probability_rev,
            risk_fwd,
            risk_rev,
            signals_fwd,
            signals_rev,
        )
        reasoning = (
            f"Impact: {impact_reasoning}\n"
            f"Probability: {probability_reasoning}\n"
            f"Risks: {risk_reasoning}\n"
            f"Signals/actionability: {signals_reasoning}"
        )

        assessments.append(
            Assessment(
                scenario_id=scenario.id,
                impact=impact,
                probability=probability,
                confidence=confidences[i],
                reasoning=reasoning,
                key_risks=key_risks,
                early_signals=early_signals,
                actionability=actionability,
                source_chunk_ids=source_ids,
            )
        )
        score_variance.append(
            {
                "scenario_id": scenario.id,
                "impact_by_pass": [impact_fwd.get("impact"), impact_rev.get("impact")],
                "probability_by_pass": [
                    probability_fwd.get("probability"),
                    probability_rev.get("probability"),
                ],
            }
        )

    metadata = {
        "position_bias_mitigation": "dual_order_average",
        "attribute_interference_mitigation": "dimension_separated_passes",
        "assessment_passes_per_batch": 6,
        "total_llm_calls": 6 * len(batches),
        "assessment_batches": len(batches),
        "batch_size": batch_size,
        "dimensions": ["impact", "probability", "risks", "early_signals_actionability"],
        "presentation_orders": {
            "batches": batches,
            "impact": "forward and reversed within each batch",
            "probability": "forward and reversed within each batch",
            "risks": "forward within each batch",
            "early_signals_actionability": "forward within each batch",
        },
        "position_bias_metadata": {
            "averaged_dimensions": ["impact", "probability"],
            "qualitative_dimensions_single_pass": ["risks", "early_signals_actionability"],
            "averaging_scope": "within each evaluation batch",
            "interpretation": (
                "Large differences between forward and reversed numeric scores indicate "
                "residual position sensitivity."
            ),
        },
        "evidence_context": {
            "strategy": "scenario_source_chunks_plus_driver_chunks_with_rag_fallback",
            "max_chunks_per_scenario": MAX_EVIDENCE_CHUNKS_PER_SCENARIO,
            "max_chars_per_chunk": MAX_EVIDENCE_CHARS_PER_CHUNK,
        },
        "score_variance_by_scenario": score_variance,
    }
    return assessments, metadata


def run(
    scenario_state_path: str = "data/outputs/scenario_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    kb_state_path: str = "data/outputs/kb_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    output_path: str = "data/outputs/final_analysis.json",
) -> dict:
    with open(scenario_state_path) as f:
        scenarios = [Scenario(**s) for s in json.load(f)["scenarios"]]
    with open(merge_state_path) as f:
        drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]
    with open(kb_state_path):
        pass  # reserved for future KB-aware evaluation hooks
    cib_state = load_cib_state(cib_state_path)

    assessments, metadata = assess_scenarios(scenarios, drivers, cib_state=cib_state)

    output = {
        "assessments": [a.model_dump() for a in assessments],
        "evaluation_metadata": metadata,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    return output
