"""Cross-Impact Balance (CIB) Matrix pipeline step.

Evaluates pairwise driver interactions using split-scoring (promoting/inhibiting)
to build a cross-impact matrix. Uses driver-to-driver evaluation.

Input: data/outputs/merge_state.json
Output: data/outputs/cib_state.json
"""

from __future__ import annotations

import json

from src.llm import safe_chat_json
from src.models.drivers import TechDriver
from src.models.scenarios import CIBEntry
from src.prompts.cib import CIB_EVALUATE
from src.rag import format_rag_chunks, retrieve


def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    output_path: str = "data/outputs/cib_state.json",
    collection=None,
    model: str | None = None,
) -> dict:
    with open(merge_state_path) as f:
        merge_state = json.load(f)

    drivers = [TechDriver(**d) for d in merge_state["unified_drivers"]]
    n = len(drivers)

    matrix = [[0] * n for _ in range(n)]
    entries: list[dict] = []
    driver_ids = [d.id for d in drivers]

    for i, da in enumerate(drivers):
        for j, db in enumerate(drivers):
            if i == j:
                continue

            rag_text = ""
            if collection is not None:
                chunks = retrieve(collection, f"{da.name} {db.name}", n=3)
                rag_text = format_rag_chunks(chunks)

            prompt = CIB_EVALUATE.format(
                driver_a_name=da.name,
                driver_a_description=da.description[:200],
                driver_b_name=db.name,
                driver_b_description=db.description[:200],
                rag_chunks=rag_text,
            )

            result = safe_chat_json(prompt, model=model)
            pro = result.get("promoting_score", 0)
            inh = result.get("inhibiting_score", 0)
            score = max(-3, min(3, pro - inh))

            matrix[i][j] = score
            source_ids = result.get("source_chunk_ids_used", [])

            entries.append(
                CIBEntry(
                    driver_a_id=da.id,
                    driver_b_id=db.id,
                    impact_score=score,
                    reasoning=f"Pro({pro}): {result.get('promoting_reasoning', '')} | Inh({inh}): {result.get('inhibiting_reasoning', '')}",
                    source_chunk_ids=source_ids,
                ).model_dump(mode="json")
            )

    influence = {d.id: sum(matrix[i]) for i, d in enumerate(drivers)}
    dependence = {d.id: sum(matrix[j][i] for j in range(n)) for i, d in enumerate(drivers)}

    cib_state = {
        "matrix": matrix,
        "driver_ids": driver_ids,
        "driver_names": [d.name for d in drivers],
        "entries": entries,
        "influence": influence,
        "dependence": dependence,
    }

    with open(output_path, "w") as f:
        json.dump(cib_state, f, indent=2)

    return cib_state
