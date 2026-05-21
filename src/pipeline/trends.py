"""Trend Scanning pipeline step.

Input: data/outputs/kb_state.json (or fixture)
Output: data/outputs/trend_state.json

Owner: Branch 2 (feature/driver-finding)
"""
from __future__ import annotations

import json
import os
import re

from src.config import CHROMA_PERSIST_DIR, MAX_RAG_CHUNKS
from src.llm import embed, safe_chat_json
from src.models.drivers import TechDriver, DriverOrigin, DriverConfidence
from src.models.common import KBPool, stable_id
from src.rag import get_collection, retrieve, format_rag_chunks
from src.prompts.trends import TREND_SCAN, TREND_IMPACT

SCAN_QUERIES = [
    "AI machine learning spectrum monitoring future trends",
    "quantum sensing RF detection new technology",
    "6G spectrum management cognitive radio",
    "space satellite spectrum monitoring",
    "edge computing distributed sensor networks",
]


def normalize_name(name: str) -> str:
    """Normalize a trend name for deduplication.

    Extracted from NB03 Cell 6.
    """
    name = name.lower().strip()
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def scan_trends(collection) -> list[dict]:
    """Scan for trends across multiple queries.

    Extracted from NB03 Cell 4.
    """
    all_trends: list[dict] = []

    for query in SCAN_QUERIES:
        rag_chunks = retrieve(collection, query, pool="trend", n=4)
        rag_text = format_rag_chunks(rag_chunks)

        prompt = TREND_SCAN.format(rag_chunks=rag_text)
        result = safe_chat_json(
            prompt,
            system="You are a technology foresight analyst identifying trends relevant to regulatory spectrum monitoring.",
        )

        chunk_ids = result.get("source_chunk_ids_used", [])
        for trend in result.get("trends", []):
            trend["source_chunk_ids"] = chunk_ids
            all_trends.append(trend)

    print(f"Found {len(all_trends)} raw trends")
    return all_trends


def assess_and_filter(
    trends: list[dict],
    collection,
) -> list[TechDriver]:
    """Assess impact of each trend, keep high/medium.

    Extracted from NB03 Cell 6.
    """
    trend_drivers: list[TechDriver] = []

    for trend in trends:
        rag_chunks = retrieve(
            collection,
            f"{trend['name']} {trend['description']}",
            pool="trend",
            n=3,
        )
        rag_text = format_rag_chunks(rag_chunks)

        prompt = TREND_IMPACT.format(
            trend_name=trend["name"],
            trend_description=trend["description"],
            rag_chunks=rag_text,
        )
        result = safe_chat_json(
            prompt,
            system="You are assessing how technology trends impact regulatory frequency monitoring.",
        )

        impact = result.get("impact_level", "none")
        print(f"  [{impact.upper():6s}] {trend['name']}")
        print(f"    -> {result.get('impact_description', '')[:100]}")

        if impact in ("high", "medium"):
            driver = TechDriver(
                id=stable_id(trend["name"], "trend"),
                name=trend["name"],
                description=f"{trend['description']}. Impact: {result.get('impact_description', '')}",
                origin=DriverOrigin.TREND,
                confidence=DriverConfidence.LOW,
                source_chunk_ids=trend.get("source_chunk_ids", []),
            )
            trend_drivers.append(driver)

    print(f"\n=== {len(trend_drivers)} Trend Drivers (high/medium impact) ===")
    return trend_drivers


def run(
    kb_state_path: str = "data/outputs/kb_state.json",
    output_path: str = "data/outputs/trend_state.json",
) -> dict:
    """Run full trend scanning pipeline."""
    collection = get_collection()

    raw_trends = scan_trends(collection)

    # Deduplicate by normalized name
    seen: set[str] = set()
    unique: list[dict] = []
    for t in raw_trends:
        key = normalize_name(t["name"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    print(f"After dedup: {len(unique)} unique trends (from {len(raw_trends)} raw)\n")

    trend_drivers = assess_and_filter(unique, collection)

    state = {
        "trend_drivers": [d.model_dump(mode="json") for d in trend_drivers],
        "all_trends_raw": unique,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nSaved {len(trend_drivers)} trend drivers")
    return state
