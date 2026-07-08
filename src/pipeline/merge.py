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
from src.models.drivers import TechDriver, DriverOrigin, DriverConfidence, DimensionType
from src.models.common import stable_id
from src.models.domain import DomainProfile
from src.prompts.merge import MERGE_DRIVERS

SIMILARITY_THRESHOLD = 0.85

_CLASSIFY_PROMPT = """Classify this technology driver into exactly ONE dimension type.

DRIVER: {name}
DESCRIPTION: {description}
ORIGIN: {origin}

DIMENSION TYPES:
- hardware: Physical components, subsystems, devices, board-level technology
- software: Algorithms, AI/ML, software, data pipelines, automation
- regulatory: Standards, regulations, compliance, certification, policy
- market: Customer demand, competitive dynamics, pricing, adoption trends
- geopolitical: National sovereignty, international cooperation, trade restrictions

Return JSON:
{{"dimension_type": "hardware" or "software" or "regulatory" or "market" or "geopolitical"}}"""


def classify_drivers(drivers: list[TechDriver]) -> list[TechDriver]:
    """Classify each driver by ontological dimension type via LLM."""
    for d in drivers:
        if d.dimension_type != DimensionType.UNCLASSIFIED:
            continue
        result = safe_chat_json(
            _CLASSIFY_PROMPT.format(
                name=d.name,
                description=d.description[:300],
                origin=d.origin.value,
            ),
            system="Classify the technology driver into exactly one dimension type.",
        )
        dim = result.get("dimension_type", "unclassified")
        try:
            d.dimension_type = DimensionType(dim)
        except ValueError:
            d.dimension_type = DimensionType.UNCLASSIFIED
    return drivers

CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def _same_dim(a: TechDriver, b: TechDriver) -> bool:
    """True if the two drivers may be consolidated: either is UNCLASSIFIED, or they match.
    Distinct classified dimensions are independent morphological axes — never collapse them."""
    return (
        a.dimension_type == DimensionType.UNCLASSIFIED
        or b.dimension_type == DimensionType.UNCLASSIFIED
        or a.dimension_type == b.dimension_type
    )


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def llm_match(bom_drivers: list[TechDriver], trend_drivers: list[TechDriver],
              profile: DomainProfile | None = None) -> dict:
    """LLM-based matching of BOM and Trend driver lists. Returns merge_result dict."""
    pkw = (profile or DomainProfile(domain="this technology domain")).prompt_kwargs()
    bom_list = "\n".join(
        [f"- Index: {i} | [{d.dimension_type.value}] Name: {d.name} | Desc: {d.description[:150]}" for i, d in enumerate(bom_drivers)]
    )
    trend_list = "\n".join(
        [f"- Index: {i} | [{d.dimension_type.value}] Name: {d.name} | Desc: {d.description[:150]}" for i, d in enumerate(trend_drivers)]
    )

    merge_prompt = MERGE_DRIVERS.format(bom_drivers=bom_list, trend_drivers=trend_list, **pkw)
    merge_prompt = merge_prompt.replace("bom_driver_id", "bom_driver_index").replace("trend_driver_id", "trend_driver_index")
    merge_prompt = merge_prompt.replace("bom driver ids", "bom driver indices").replace("trend driver ids", "trend driver indices")

    merge_result = safe_chat_json(
        merge_prompt,
        system=f"You are merging two technology driver lists for {pkw['domain']}. Use the INDEX numbers provided, not names or made-up IDs.",
    )

    matched_bom_indices: set[int] = set()
    matched_trend_indices: set[int] = set()
    valid_matches = []

    for m in merge_result.get("matches", []):
        try:
            bi = int(m.get("bom_driver_index"))
            ti = int(m.get("trend_driver_index"))
        except (TypeError, ValueError):
            continue
        if bi < 0 or bi >= len(bom_drivers):
            continue
        if ti < 0 or ti >= len(trend_drivers):
            continue
        # Reject cross-type matches — different dimension types are independent morphological axes
        bom_type = bom_drivers[bi].dimension_type
        trend_type = trend_drivers[ti].dimension_type
        if bom_type != DimensionType.UNCLASSIFIED and trend_type != DimensionType.UNCLASSIFIED and bom_type != trend_type:
            print(f"  Rejected cross-type match: [{bom_type.value}] {bom_drivers[bi].name} <-> [{trend_type.value}] {trend_drivers[ti].name}", flush=True)
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
        dim_type = bom_d.dimension_type if bom_d.dimension_type != DimensionType.UNCLASSIFIED else trend_d.dimension_type
        driver = TechDriver(
            id=stable_id(m["unified_name"], "both"),
            name=m["unified_name"],
            description=f"BOM: {bom_d.description[:200]} | Trend: {trend_d.description[:200]}",
            origin=DriverOrigin.BOTH,
            confidence=DriverConfidence.HIGH,
            dimension_type=dim_type,
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
        # MEDIUM (not LOW): external regulatory/environmental forces are core foresight
        # inputs and deserve equal footing with unvalidated BOM components in consolidation.
        d.confidence = DriverConfidence.MEDIUM
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
            if sim_matrix[i][j] > SIMILARITY_THRESHOLD and _same_dim(unified_drivers[i], unified_drivers[j]):
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
                if idx != best_idx and _same_dim(rep, unified_drivers[idx]):
                    rep.source_chunk_ids = list(set(rep.source_chunk_ids + unified_drivers[idx].source_chunk_ids))
                    remove_indices.add(idx)
        unified_drivers = [d for i, d in enumerate(unified_drivers) if i not in remove_indices]

    return unified_drivers


def run(
    bom_state_path: str = "data/outputs/bom_state.json",
    trend_state_path: str = "data/outputs/trend_state.json",
    output_path: str = "data/outputs/merge_state.json",
    profile: DomainProfile | None = None,
) -> dict:
    """Run full merge pipeline: LLM match → build unified list → 3-stage consolidation."""
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    with open(bom_state_path) as f:
        bom_drivers = [TechDriver(**d) for d in json.load(f)["bom_drivers"]]
    with open(trend_state_path) as f:
        trend_drivers = [TechDriver(**d) for d in json.load(f)["trend_drivers"]]

    print(f"  Classifying {len(bom_drivers)} BOM + {len(trend_drivers)} trend drivers by dimension type...")
    classify_drivers(bom_drivers)
    classify_drivers(trend_drivers)
    for d in bom_drivers:
        print(f"    [{d.dimension_type.value:12s}] {d.name[:50]}")
    for d in trend_drivers:
        print(f"    [{d.dimension_type.value:12s}] {d.name[:50]}")

    merge_result = llm_match(bom_drivers, trend_drivers, profile)
    unified = build_unified_list(merge_result, bom_drivers, trend_drivers)
    unified = consolidate(unified)

    state = {
        "unified_drivers": [d.model_dump(mode="json") for d in unified],
        "merge_result": merge_result,
    }
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    return state
