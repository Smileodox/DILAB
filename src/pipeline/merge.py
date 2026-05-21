"""Merge Drivers pipeline step (NB04).

Input: data/outputs/bom_state.json + data/outputs/trend_state.json
Output: data/outputs/merge_state.json
"""
from __future__ import annotations
import json
import os
import re

import numpy as np

from src.llm import embed, safe_chat_json
from src.models.drivers import TechDriver, DriverOrigin, DriverConfidence
from src.models.common import stable_id
from src.prompts.merge import MERGE_DRIVERS

SIMILARITY_THRESHOLD = 0.85

CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def llm_match(bom_drivers: list[TechDriver], trend_drivers: list[TechDriver]) -> dict:
    """LLM-based matching of BOM and Trend driver lists. Returns merge_result dict."""
    bom_list = "\n".join(
        [f"- Index: {i} | Name: {d.name} | Desc: {d.description[:150]}" for i, d in enumerate(bom_drivers)]
    )
    trend_list = "\n".join(
        [f"- Index: {i} | Name: {d.name} | Desc: {d.description[:150]}" for i, d in enumerate(trend_drivers)]
    )

    merge_prompt = MERGE_DRIVERS.format(bom_drivers=bom_list, trend_drivers=trend_list)
    merge_prompt = merge_prompt.replace("bom_driver_id", "bom_driver_index").replace("trend_driver_id", "trend_driver_index")
    merge_prompt = merge_prompt.replace("bom driver ids", "bom driver indices").replace("trend driver ids", "trend driver indices")

    merge_result = safe_chat_json(
        merge_prompt,
        system="You are merging two technology driver lists for regulatory frequency monitoring. Use the INDEX numbers provided, not names or made-up IDs.",
    )

    matched_bom_indices: set[int] = set()
    matched_trend_indices: set[int] = set()
    valid_matches = []

    for m in merge_result.get("matches", []):
        bi = m.get("bom_driver_index")
        ti = m.get("trend_driver_index")
        if not isinstance(bi, int) or bi < 0 or bi >= len(bom_drivers):
            continue
        if not isinstance(ti, int) or ti < 0 or ti >= len(trend_drivers):
            continue
        valid_matches.append(m)
        matched_bom_indices.add(bi)
        matched_trend_indices.add(ti)

    merge_result["matches"] = valid_matches

    returned_bom_only = {idx for idx in merge_result.get("bom_only", []) if isinstance(idx, int) and 0 <= idx < len(bom_drivers)}
    returned_trend_only = {idx for idx in merge_result.get("trend_only", []) if isinstance(idx, int) and 0 <= idx < len(trend_drivers)}

    returned_bom_only |= set(range(len(bom_drivers))) - matched_bom_indices - returned_bom_only
    returned_trend_only |= set(range(len(trend_drivers))) - matched_trend_indices - returned_trend_only

    merge_result["bom_only"] = list(returned_bom_only)
    merge_result["trend_only"] = list(returned_trend_only)

    return merge_result


def build_unified_list(
    merge_result: dict, bom_drivers: list[TechDriver], trend_drivers: list[TechDriver],
) -> list[TechDriver]:
    """Build unified driver list with confidence tags from merge result."""
    unified: list[TechDriver] = []

    for m in merge_result.get("matches", []):
        bi = m["bom_driver_index"]
        ti = m["trend_driver_index"]
        bom_d = bom_drivers[bi]
        trend_d = trend_drivers[ti]
        merged_sources = list(set(bom_d.source_chunk_ids + trend_d.source_chunk_ids))
        driver = TechDriver(
            id=stable_id(m["unified_name"], "both"),
            name=m["unified_name"],
            description=f"BOM: {bom_d.description[:200]} | Trend: {trend_d.description[:200]}",
            origin=DriverOrigin.BOTH,
            confidence=DriverConfidence.HIGH,
            bom_node_id=bom_d.bom_node_id,
            source_chunk_ids=merged_sources,
            merge_reasoning=m.get("reasoning", ""),
        )
        unified.append(driver)

    for bi in merge_result.get("bom_only", []):
        d = bom_drivers[bi]
        d.confidence = DriverConfidence.MEDIUM
        unified.append(d)

    for ti in merge_result.get("trend_only", []):
        d = trend_drivers[ti]
        d.confidence = DriverConfidence.LOW
        unified.append(d)

    return unified


def consolidate(unified_drivers: list[TechDriver]) -> list[TechDriver]:
    """3-stage deduplication: normalized name, cosine similarity, LLM grouping."""
    # Stage 1: Normalized name dedup
    exact_seen: dict[str, int] = {}
    for i, d in enumerate(unified_drivers):
        key = normalize_name(d.name)
        if key in exact_seen:
            first = unified_drivers[exact_seen[key]]
            first.source_chunk_ids = list(set(first.source_chunk_ids + d.source_chunk_ids))
            if d.confidence.value == "high" or (d.origin.value == "both" and first.origin.value != "both"):
                first.confidence = d.confidence
                first.origin = d.origin
            unified_drivers[i] = None
        else:
            exact_seen[key] = i
    unified_drivers = [d for d in unified_drivers if d is not None]

    # Stage 2: Cosine similarity dedup
    texts = [f"{d.name}: {d.description[:150]}" for d in unified_drivers]
    embeddings = np.array(embed(texts))
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    sim_matrix = (embeddings @ embeddings.T) / (norms @ norms.T + 1e-10)

    merged_indices: set[int] = set()
    consolidated: list[TechDriver] = []

    for i in range(len(unified_drivers)):
        if i in merged_indices:
            continue
        cluster = [i]
        for j in range(i + 1, len(unified_drivers)):
            if j in merged_indices:
                continue
            if sim_matrix[i][j] > SIMILARITY_THRESHOLD:
                cluster.append(j)
                merged_indices.add(j)

        best_idx = max(cluster, key=lambda idx: (
            CONF_RANK.get(unified_drivers[idx].confidence.value, 0),
            len(unified_drivers[idx].source_chunk_ids),
        ))
        rep = unified_drivers[best_idx]
        all_sources: set[str] = set()
        for idx in cluster:
            all_sources.update(unified_drivers[idx].source_chunk_ids)
        rep.source_chunk_ids = list(all_sources)
        consolidated.append(rep)

    unified_drivers = consolidated

    # Stage 3: LLM semantic grouping
    driver_list = "\n".join([f"  {i}. {d.name}" for i, d in enumerate(unified_drivers)])
    grouping_prompt = f"""You have {len(unified_drivers)} technology drivers for regulatory frequency monitoring.
Identify groups of drivers that describe the SAME or highly overlapping technology concept.

RULES:
- Only group drivers that are truly semantically redundant (same core technology, just named differently)
- Do NOT group drivers that are related but distinct
- Do NOT merge BOM hardware components that are physically different subsystems
- If a driver is unique, it should not appear in any group

DRIVERS:
{driver_list}

Return JSON:
{{
  "groups": [
    {{
      "indices": [list of driver indices that should be merged],
      "best_name": "the best name for the merged driver",
      "reasoning": "why these are the same technology"
    }}
  ]
}}

Only include groups with 2+ members. If no duplicates remain, return {{"groups": []}}."""

    group_result = safe_chat_json(
        grouping_prompt,
        system="You are deduplicating a technology driver list. Be conservative — only merge true duplicates.",
    )

    groups = group_result.get("groups", [])
    if groups:
        remove_indices: set[int] = set()
        for g in groups:
            indices = g["indices"]
            best_name = g["best_name"]
            best_idx = max(indices, key=lambda idx: (
                CONF_RANK.get(unified_drivers[idx].confidence.value, 0),
                len(unified_drivers[idx].source_chunk_ids),
            ))
            rep = unified_drivers[best_idx]
            rep.name = best_name
            for idx in indices:
                if idx != best_idx:
                    rep.source_chunk_ids = list(set(rep.source_chunk_ids + unified_drivers[idx].source_chunk_ids))
                    remove_indices.add(idx)
        unified_drivers = [d for i, d in enumerate(unified_drivers) if i not in remove_indices]

    return unified_drivers


def run(
    bom_state_path: str = "data/outputs/bom_state.json",
    trend_state_path: str = "data/outputs/trend_state.json",
    output_path: str = "data/outputs/merge_state.json",
) -> dict:
    """Run full merge pipeline: LLM match → build unified list → 3-stage consolidation."""
    with open(bom_state_path) as f:
        bom_drivers = [TechDriver(**d) for d in json.load(f)["bom_drivers"]]
    with open(trend_state_path) as f:
        trend_drivers = [TechDriver(**d) for d in json.load(f)["trend_drivers"]]

    merge_result = llm_match(bom_drivers, trend_drivers)
    unified = build_unified_list(merge_result, bom_drivers, trend_drivers)
    unified = consolidate(unified)

    state = {
        "unified_drivers": [d.model_dump(mode="json") for d in unified],
        "merge_result": merge_result,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    return state
