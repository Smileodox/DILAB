"""Scenario Evaluation pipeline step."""
from __future__ import annotations
import json
import os

import numpy as np

from src.config import CHROMA_PERSIST_DIR
from src.llm import embed, safe_chat_json
from src.models.scenarios import Scenario
from src.models.evaluation import Assessment
from src.models.drivers import TechDriver, DriverConfidence
from src.rag import get_collection
from src.prompts.evaluation import SCENARIO_ASSESS

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}


def compute_scenario_confidences(scenarios: list[Scenario], driver_by_id: dict[str, TechDriver]) -> list[float]:
    """Compute confidence per scenario from driver confidences. From NB07 Cell 2."""
    confidences = []
    for scenario in scenarios:
        driver_confs = []
        for a in scenario.assumptions:
            d = driver_by_id.get(a.driver_id)
            if d:
                driver_confs.append(CONFIDENCE_MAP.get(d.confidence.value, 0.5))
        confidences.append(round(np.mean(driver_confs), 2) if driver_confs else 0.5)
    return confidences


def build_scenarios_block(scenarios: list[Scenario]) -> str:
    """Build the batch assessment prompt block. From NB07 Cell 2."""
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


def assess_scenarios(scenarios: list[Scenario], scenario_confidences: list[float], collection) -> list[Assessment]:
    """Batch-assess all scenarios via LLM. From NB07 Cell 2."""
    scenarios_block = build_scenarios_block(scenarios)

    # RAG retrieval
    combined_query = " ".join([s.title for s in scenarios])
    query_emb = embed([combined_query[:500]])[0]
    rag = collection.query(query_embeddings=[query_emb], n_results=5, include=["documents", "metadatas"])
    rag_text = "\n\n---\n\n".join([
        f"[Chunk ID: {rag['ids'][0][i]}] (Source: {rag['metadatas'][0][i]['source_title']})\n{rag['documents'][0][i]}"
        for i in range(len(rag["ids"][0]))
    ])

    prompt = SCENARIO_ASSESS.format(n=len(scenarios), scenarios_block=scenarios_block, rag_chunks=rag_text)
    result = safe_chat_json(prompt, system="You are a strategic technology analyst at Rohde & Schwarz evaluating future scenarios for spectrum monitoring.")

    assessments = []
    batch = result.get("assessments", [])
    for i, scenario in enumerate(scenarios):
        match = next((a for a in batch if a.get("scenario_index") == i), None)
        if match:
            assessment = Assessment(
                scenario_id=scenario.id,
                impact=match.get("impact", 5),
                probability=match.get("probability", 5),
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


def generate_traceability_report(scenarios: list[Scenario], assessments: list[Assessment],
                                  driver_by_id: dict, kb_state: dict) -> str:
    """Generate E2E traceability text. From NB07 Cell 6."""
    lines = ["TRACEABILITY REPORT"]
    source_by_id = kb_state["sources"]
    chunk_by_id = kb_state["chunks"]

    for scenario, assessment in zip(scenarios, assessments):
        lines.append(f"\nSCENARIO: {scenario.title}")
        lines.append(f"Type: {scenario.type.value} | Impact: {assessment.impact} | Prob: {assessment.probability}")

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


def run(
    scenario_state_path: str = "data/outputs/scenario_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    kb_state_path: str = "data/outputs/kb_state.json",
    output_path: str = "data/outputs/final_analysis.json",
) -> dict:
    """Run full scenario evaluation."""
    collection = get_collection()

    with open(scenario_state_path) as f:
        scenarios = [Scenario(**s) for s in json.load(f)["scenarios"]]
    with open(merge_state_path) as f:
        drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]
    with open(kb_state_path) as f:
        kb_state = json.load(f)

    driver_by_id = {d.id: d for d in drivers}
    confidences = compute_scenario_confidences(scenarios, driver_by_id)
    assessments = assess_scenarios(scenarios, confidences, collection)

    state = {
        "assessments": [a.model_dump(mode="json") for a in assessments],
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    return state
