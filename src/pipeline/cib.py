"""Cross-Impact Balance (CIB) Matrix pipeline step.

Pairwise evaluation: How does progress in Driver A affect Driver B?
Scale: -3 (strongly inhibits) to +3 (strongly promotes).
Each assessment includes reasoning + source references.

Input: data/outputs/merge_state.json
Output: data/outputs/cib_state.json

Owner: Branch 3 (feature/scenario-generation)
Extracted from: notebooks/05_cib_matrix.ipynb
"""
from __future__ import annotations

import json
import os
from collections import Counter

import numpy as np

from src.config import CHROMA_PERSIST_DIR, MAX_RAG_CHUNKS, CIB_MODEL
from src.llm import embed, safe_chat_json
from src.models.drivers import TechDriver
from src.models.scenarios import CIBEntry
from src.rag import get_collection
from src.prompts.cib import CIB_EVALUATE


def retrieve_for_pair(collection, driver_a: str, driver_b: str, n: int = 3) -> str:
    """RAG retrieval for a driver pair. From NB05 Cell 2."""
    query = f"{driver_a} {driver_b} relationship impact influence"
    query_emb = embed([query])[0]
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=n,
        include=["documents", "metadatas"],
    )
    parts = []
    for i in range(len(results["ids"][0])):
        parts.append(
            f"[Chunk ID: {results['ids'][0][i]}] "
            f"(Source: {results['metadatas'][0][i]['source_title']})\n"
            f"{results['documents'][0][i]}"
        )
    return "\n\n---\n\n".join(parts)


def evaluate_matrix(
    drivers: list[TechDriver], collection
) -> tuple[np.ndarray, list[CIBEntry]]:
    """Evaluate all directed driver pairs. From NB05 Cell 2.

    Returns (matrix, entries).
    """
    n = len(drivers)
    matrix = np.zeros((n, n), dtype=int)
    entries: list[CIBEntry] = []

    for i, da in enumerate(drivers):
        for j, db in enumerate(drivers):
            if i == j:
                continue

            rag_text = retrieve_for_pair(collection, da.name, db.name)
            prompt = CIB_EVALUATE.format(
                driver_a_name=da.name,
                driver_a_description=da.description[:200],
                driver_b_name=db.name,
                driver_b_description=db.description[:200],
                rag_chunks=rag_text,
            )
            result = safe_chat_json(
                prompt,
                system="You are evaluating cross-impacts between technology drivers in spectrum monitoring.",
                model=CIB_MODEL,
                temperature=0.2,
            )

            pro = max(0, min(3, result.get("promoting_score", 0)))
            inh = max(0, min(3, result.get("inhibiting_score", 0)))
            score = max(-3, min(3, pro - inh))
            matrix[i][j] = score

            reasoning = (
                f"Pro({pro}): {result.get('promoting_reasoning', '')} | "
                f"Inh({inh}): {result.get('inhibiting_reasoning', '')}"
            )
            entry = CIBEntry(
                driver_a_id=da.id,
                driver_b_id=db.id,
                impact_score=score,
                reasoning=reasoning,
                source_chunk_ids=result.get("source_chunk_ids_used", []),
            )
            entries.append(entry)

        print(f"  Row {i + 1}/{n}: {da.name[:40]} -> scores: {matrix[i].tolist()}")

    # Score distribution analysis
    all_scores = [matrix[i][j] for i in range(n) for j in range(n) if i != j]
    dist = Counter(all_scores)
    print(f"\n=== Score Distribution ===")
    for s in range(-3, 4):
        count = dist.get(s, 0)
        pct = count / len(all_scores) * 100 if all_scores else 0
        print(f"  {s:+d}: {count:3d} ({pct:4.1f}%)")
    neg_count = sum(1 for s in all_scores if s < 0)
    print(f"\nNegative scores: {neg_count}/{len(all_scores)} ({neg_count / len(all_scores) * 100:.1f}%)")
    print(f"Mean score: {np.mean(all_scores):.2f}")

    return matrix, entries


def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    output_path: str = "data/outputs/cib_state.json",
) -> dict:
    """Run full CIB evaluation.

    Loads drivers from merge_state, evaluates all pairwise cross-impacts
    via LLM + RAG, and saves the CIB matrix with influence/dependence scores.
    """
    collection = get_collection()

    with open(merge_state_path) as f:
        drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]

    print(f"All drivers: {len(drivers)}")
    print(f"CIB pairs: {len(drivers) * (len(drivers) - 1)}")
    print(f"Using model: {CIB_MODEL}")

    matrix, entries = evaluate_matrix(drivers, collection)

    n = len(drivers)
    influence = matrix.sum(axis=1)
    dependence = matrix.sum(axis=0)

    print("\n=== Driver Influence Ranking ===")
    for idx in np.argsort(influence)[::-1]:
        d = drivers[idx]
        print(f"  Influence: {influence[idx]:+3d} | Dependence: {dependence[idx]:+3d} | {d.name}")

    state = {
        "matrix": matrix.tolist(),
        "driver_ids": [d.id for d in drivers],
        "driver_names": [d.name for d in drivers],
        "entries": [e.model_dump(mode="json") for e in entries],
        "influence": {drivers[i].id: int(influence[i]) for i in range(n)},
        "dependence": {drivers[i].id: int(dependence[i]) for i in range(n)},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Saved CIB matrix ({n}x{n}) with {len(entries)} entries")
    return state
