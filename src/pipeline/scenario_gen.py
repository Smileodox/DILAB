"""Scenario Generation pipeline step (morphological approach).

Generates scenarios from CIB-consistent manifestation configurations.

Input: consistency_state.json + morphbox_state.json + cib_state.json + merge_state.json
Output: data/outputs/scenario_state.json
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from src import config
from src.llm import embed, safe_chat_json
from src.models.drivers import TechDriver
from src.models.morphological import DriverManifestation, MorphologicalBox
from src.models.scenarios import DriverAssumption, Scenario, ScenarioType
from src.prompts.morphological import (
    SCENARIO_GENERATE_MORPHOLOGICAL,
    SCENARIO_GENERATE_MORPHOLOGICAL_NEUTRAL,
    SCENARIO_GENERATE_MORPHOLOGICAL_SHORT,
)
from src.prompts.scenarios import (
    SCENARIO_NARRATIVE_GUIDE,
    SCENARIO_NARRATIVE_GUIDE_SHORT,
)

log = logging.getLogger(__name__)


def _manif_pos(morph_box: MorphologicalBox, driver_id: str, manif_id: str) -> float:
    ids = morph_box.manifestations[driver_id]
    n = len(ids)
    if n <= 1:
        return 0.5
    return ids.index(manif_id) / (n - 1)


def _anchor_drivers(
    config: dict[str, str],
    morph_box: MorphologicalBox,
    manif_lookup: dict,
    driver_by_id: dict,
    stype: ScenarioType,
    n: int = 3,
) -> str:
    """Return the most characterising drivers for this config as narrative anchors.

    Cautionary → most pessimistic; disruptive → most optimistic;
    wildcard → both extremes; evolutionary → most central.
    """
    scored = []
    for d_id, m_id in config.items():
        driver = driver_by_id.get(d_id)
        manif = manif_lookup.get(m_id)
        if not driver or not manif:
            continue
        pos = _manif_pos(morph_box, d_id, m_id)
        scored.append((pos, driver, manif))

    if stype == ScenarioType.CAUTIONARY:
        anchors = sorted(scored, key=lambda x: -x[0])[:n]
    elif stype == ScenarioType.DISRUPTIVE:
        anchors = sorted(scored, key=lambda x: x[0])[:n]
    elif stype == ScenarioType.WILDCARD:
        by_pos = sorted(scored, key=lambda x: x[0])
        anchors = (by_pos[:2] + by_pos[-2:])[:n]
    else:
        anchors = sorted(scored, key=lambda x: abs(x[0] - 0.5))[:n]

    return "\n".join(
        f"- {drv.name}: **{manif.label}** — {manif.description[:200]}"
        for _, drv, manif in anchors
    )


def verify_narrative_coverage(scenario: Scenario, manif_lookup: dict) -> float:
    """Check how many driver manifestation labels appear in the narrative."""
    narrative_lower = scenario.narrative.lower()
    hits = 0
    for a in scenario.assumptions:
        m = manif_lookup.get(a.manifestation_id)
        if not m:
            continue
        if m.label.lower() in narrative_lower:
            hits += 1
            continue
        words = [w for w in m.label.lower().split() if len(w) > 5]
        if words and any(w in narrative_lower for w in words):
            hits += 1
            continue
        log.debug("Scenario '%s' missing driver: %s", scenario.title[:40], m.label)
    total = max(len(scenario.assumptions), 1)
    ratio = hits / total
    if ratio < 0.7:
        log.warning(
            "Low coverage %.0f%% for '%s' (%d/%d drivers mentioned)",
            ratio * 100, scenario.title[:40], hits, total,
        )
    return round(ratio, 3)


def run(
    consistency_state_path: str = "data/outputs/consistency_state.json",
    morphbox_state_path: str = "data/outputs/morphbox_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    output_path: str = "data/outputs/scenario_state.json",
    narrative_mode: str = "full",
    max_workers: int | None = None,
    collection=None,
    model: str | None = None,
) -> dict:
    # Read module config here: inside _generate_one the name `config` is the local
    # seed configuration dict, so the module attr must be captured in run() scope.
    combi_words = config.COMBI_NARRATIVE_WORDS

    with open(consistency_state_path) as f:
        consistency = json.load(f)
    with open(morphbox_state_path) as f:
        morphbox_raw = json.load(f)
    with open(cib_state_path) as f:
        cib = json.load(f)
    with open(merge_state_path) as f:
        merge_state = json.load(f)

    morph_box = MorphologicalBox(
        drivers=morphbox_raw["drivers"],
        manifestations=morphbox_raw["manifestations"],
        all_manifestations=[
            DriverManifestation(**m) for m in morphbox_raw["all_manifestations"]
        ],
    )
    drivers = [TechDriver(**d) for d in merge_state["unified_drivers"]]
    driver_by_id = {d.id: d for d in drivers}
    manif_lookup = {m.id: m for m in morph_box.all_manifestations}

    cib_matrix = np.array(cib["matrix"])
    cib_id_to_idx = {did: i for i, did in enumerate(cib["driver_ids"])}

    seeds = consistency["configs"]

    completed_titles: list[str] = []
    titles_lock = threading.Lock()
    used_chunk_ids: set[str] = set()
    used_chunk_ids_lock = threading.Lock()

    def _generate_one(seed_idx: int, seed: dict) -> Scenario:
        stype_str = seed.get("scenario_type", "evolutionary")
        stype = (
            ScenarioType(stype_str)
            if stype_str in [e.value for e in ScenarioType]
            else ScenarioType.EVOLUTIONARY
        )
        config = seed["configuration"]
        seed_id = seed.get("id", "")
        is_fp = seed.get("is_fixed_point", True)

        assumptions = []
        manif_block_parts = []
        for d_id, m_id in config.items():
            driver = driver_by_id.get(d_id)
            manif = manif_lookup.get(m_id)
            if not driver or not manif:
                continue
            assumptions.append(
                DriverAssumption(
                    driver_id=d_id,
                    manifestation_id=m_id,
                    state=manif.label,
                    description=f"{driver.name}: {manif.label} — {manif.description}",
                )
            )
            manif_block_parts.append(
                f"- {driver.name}: **{manif.label}**\n  {manif.description}"
            )

        cib_parts = []
        for did_a in config:
            idx_a = cib_id_to_idx.get(did_a)
            if idx_a is None:
                continue
            da = driver_by_id.get(did_a)
            for did_b in config:
                if did_a == did_b:
                    continue
                idx_b = cib_id_to_idx.get(did_b)
                if idx_b is None:
                    continue
                score = int(cib_matrix[idx_a][idx_b])
                if abs(score) >= 1:
                    db = driver_by_id.get(did_b)
                    effect = {
                        2: "strongly promotes",
                        1: "mildly promotes",
                        -1: "mildly inhibits",
                    }.get(score, "strongly inhibits" if score < -1 else "strongly promotes")
                    cib_parts.append(
                        f"- {da.name[:40]} {effect} {db.name[:40]} (score: {score:+d})"
                    )

        rag_text = ""
        rag_chunk_ids: list[str] = []
        if collection is not None:
            query_parts = [
                f"{manif_lookup[config[d_id]].label} {driver_by_id[d_id].name[:30]}"
                for d_id in config
                if d_id in driver_by_id and config[d_id] in manif_lookup
            ]
            query_text = f"{' '.join(query_parts)} spectrum monitoring 2035"
            query_emb = embed([query_text[:500]])[0]
            rag = collection.query(
                query_embeddings=[query_emb],
                n_results=8,
                include=["documents", "metadatas"],
            )
            with used_chunk_ids_lock:
                novel = [
                    (rag["ids"][0][j], rag["documents"][0][j], rag["metadatas"][0][j])
                    for j in range(len(rag["ids"][0]))
                    if rag["ids"][0][j] not in used_chunk_ids
                ]
                reused = [
                    (rag["ids"][0][j], rag["documents"][0][j], rag["metadatas"][0][j])
                    for j in range(len(rag["ids"][0]))
                    if rag["ids"][0][j] in used_chunk_ids
                ]
                ranked = (novel + reused)[:5]
                used_chunk_ids.update(cid for cid, _, _ in ranked)
            rag_text = "\n\n---\n\n".join(
                [
                    f"[Chunk ID: {cid}] (Source: {meta['source_title']})\n{doc}"
                    for cid, doc, meta in ranked
                ]
            )
            rag_chunk_ids = [cid for cid, _, _ in ranked]

        anchors = _anchor_drivers(config, morph_box, manif_lookup, driver_by_id, stype)

        with titles_lock:
            existing = ", ".join(f'"{t}"' for t in completed_titles) if completed_titles else ""
        titles_block = f"Previously generated titles (yours MUST differ): {existing}" if existing else ""

        cib_context = "\n".join(cib_parts) if cib_parts else "No notable cross-impacts."

        if narrative_mode == "short":
            # Bottom-up / combinatorial path: one neutral, less-speculative guide,
            # shorter target, lower temperature. Anchors still use the inferred type's
            # rule so the snapshot highlights this combination's characterising drivers.
            narrative_guide = SCENARIO_NARRATIVE_GUIDE_SHORT.format(
                anchor_drivers=anchors, word_count=combi_words
            )
            prompt = SCENARIO_GENERATE_MORPHOLOGICAL_SHORT.format(
                driver_manifestations_block="\n".join(manif_block_parts),
                existing_titles_block=titles_block,
                cib_context=cib_context,
                rag_chunks=rag_text,
                narrative_guide=narrative_guide,
                word_count=combi_words,
            )
            temperature = 0.5
        elif narrative_mode == "neutral":
            # Non-leading prompt: no length squeeze, no "don't speculate", no
            # "make it distinct" — let the model render the configuration as it sees fit.
            prompt = SCENARIO_GENERATE_MORPHOLOGICAL_NEUTRAL.format(
                driver_manifestations_block="\n".join(manif_block_parts),
                existing_titles_block=titles_block,
                cib_context=cib_context,
                rag_chunks=rag_text,
            )
            temperature = 0.7
        else:
            narrative_guide = SCENARIO_NARRATIVE_GUIDE.get(
                stype.value, SCENARIO_NARRATIVE_GUIDE["evolutionary"]
            ).format(anchor_drivers=anchors)
            prompt = SCENARIO_GENERATE_MORPHOLOGICAL.format(
                driver_manifestations_block="\n".join(manif_block_parts),
                scenario_type=stype.value,
                existing_titles_block=titles_block,
                cib_context=cib_context,
                rag_chunks=rag_text,
                narrative_guide=narrative_guide,
            )
            temperature = 0.75

        result = safe_chat_json(prompt, temperature=temperature, model=model)

        all_source_ids = list(set(rag_chunk_ids + result.get("source_chunk_ids_used", [])))
        for a in assumptions:
            m = manif_lookup.get(a.manifestation_id)
            if m:
                all_source_ids.extend(m.source_chunk_ids)
        all_source_ids = list(set(all_source_ids))

        scenario = Scenario(
            title=result.get("title", "Untitled"),
            narrative=result.get("narrative", ""),
            type=stype,
            perspective=result.get("perspective", ""),
            key_tensions=result.get("key_tensions", []),
            assumptions=assumptions,
            source_chunk_ids=all_source_ids,
            seed_id=seed_id,
            is_fixed_point=is_fp,
        )

        scenario.coverage_ratio = verify_narrative_coverage(scenario, manif_lookup)

        with titles_lock:
            completed_titles.append(scenario.title)

        print(f"  Scenario {seed_idx + 1}/{len(seeds)} done: {scenario.title[:50]} (coverage: {scenario.coverage_ratio:.0%})")
        return scenario

    with ThreadPoolExecutor(max_workers=max_workers or min(8, len(seeds))) as pool:
        futures = {
            pool.submit(_generate_one, i, seed): i for i, seed in enumerate(seeds)
        }
        scenarios: list[Scenario] = [None] * len(seeds)
        for future in as_completed(futures):
            idx = futures[future]
            scenarios[idx] = future.result()

    scenario_state = {
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
    }
    with open(output_path, "w") as f:
        json.dump(scenario_state, f, indent=2)

    return scenario_state
