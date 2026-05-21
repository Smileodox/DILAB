"""Scenario Generation pipeline step.

Generate future scenarios using CIB-based clustering:
1. Cluster drivers via hierarchical clustering on CIB interaction profiles
2. LLM archetype generation from cluster data + influence ranking + tension pairs
3. CIB consistency check validates state combinations
4. Scenario narratives grounded in RAG + CIB context

Input: data/outputs/merge_state.json + data/outputs/cib_state.json
Output: data/outputs/scenario_state.json

Owner: Branch 3 (feature/scenario-generation)
Extracted from: notebooks/06_scenario_generation.ipynb
"""
from __future__ import annotations

import json
import os

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

from src.config import CHROMA_PERSIST_DIR
from src.llm import safe_chat_json, embed
from src.models.drivers import TechDriver
from src.models.scenarios import (
    CIBEntry,
    DriverAssumption,
    Scenario,
    ScenarioType,
)
from src.rag import get_collection
from src.prompts.scenarios import SCENARIO_GENERATE, SCENARIO_NARRATIVE_GUIDE


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

N_CLUSTERS = 4

SYSTEM_PROMPTS: dict[str, str] = {
    "evolutionary": (
        "You are a pragmatic technology analyst writing grounded future scenarios "
        "for spectrum monitoring. Focus on operational realities, incremental changes, "
        "and practical constraints."
    ),
    "disruptive": (
        "You are a technology foresight expert writing vivid future scenarios for "
        "spectrum monitoring. Explore both the promise and the disruption costs of "
        "breakthrough technologies."
    ),
    "cautionary": (
        "You are a critical technology analyst writing scenarios that examine what "
        "can go wrong with promising technologies. Focus on deployment barriers, "
        "organizational resistance, cost overruns, regulatory lag, and unintended "
        "consequences."
    ),
    "wildcard": (
        "You are a scenario planner exploring unlikely but plausible futures for "
        "spectrum monitoring. Focus on surprising developments, cascading effects, "
        "and second-order consequences."
    ),
}

ARCHETYPE_PROMPT_TEMPLATE = """Based on this CIB analysis of {n_cib} technology drivers for regulatory frequency monitoring:

DRIVER CLUSTERS (from cross-impact analysis):
{cluster_descriptions}

INFLUENCE RANKING (system enablers at top):
{influence_text}

TENSIONS (negative cross-impacts):
{tension_text}

Propose exactly 6 scenario archetypes for horizon 2035. You MUST include:
- Exactly 2 EVOLUTIONARY scenarios (incremental progress, no breakthroughs dominate)
- Exactly 1 DISRUPTIVE scenario (one or more technology clusters achieve breakthrough, transforming the field)
- Exactly 1 CAUTIONARY scenario (promising technologies face deployment barriers, cost constraints, regulatory failure, organizational resistance, or unintended consequences — this is NOT just "stagnation" but active failure or negative outcomes)
- Exactly 1 WILDCARD scenario (low-probability event: geopolitical disruption, unexpected regulatory shift, supply chain collapse, or paradigm-breaking scientific discovery)
- Exactly 1 scenario of your choice (any type)

Rules:
- Every scenario must have at least 2 different states across clusters
- At least one scenario should have a cluster at "stagnation"
- The CAUTIONARY scenario should explore how even "breakthrough" technologies can fail to deliver value
- The WILDCARD scenario should explore a genuinely surprising development, not just "more technology"
- Justify each state assignment from the CIB data

For each archetype, provide a "perspective" — a 3-5 word framing phrase that captures the core narrative angle (e.g., "regulatory overreach stifles innovation", "quantum sensing reshapes enforcement", "cost barriers fragment adoption", "geopolitical tensions disrupt supply chains").

Return JSON:
{{
  "archetypes": [
    {{
      "short_name": "concise scenario name",
      "scenario_type": "evolutionary" or "disruptive" or "cautionary" or "wildcard",
      "perspective": "3-5 word framing phrase",
      "cluster_states": {{
        "1": "breakthrough/steady_progress/stagnation",
        "2": "breakthrough/steady_progress/stagnation",
        "3": "breakthrough/steady_progress/stagnation",
        "4": "breakthrough/steady_progress/stagnation"
      }},
      "rationale": "why these states, referencing CIB clusters and tensions"
    }}
  ]
}}"""


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_drivers(cib_matrix: np.ndarray) -> dict[int, list[int]]:
    """Hierarchical clustering on CIB matrix rows. From NB06 Cell 2.

    Returns mapping of cluster label -> list of driver indices.
    """
    n_cib = cib_matrix.shape[0]

    dist_matrix = np.zeros((n_cib, n_cib))
    for i in range(n_cib):
        for j in range(n_cib):
            dist_matrix[i][j] = np.linalg.norm(cib_matrix[i] - cib_matrix[j])

    condensed = squareform(dist_matrix)
    Z = linkage(condensed, method="ward")
    cluster_labels = fcluster(Z, t=N_CLUSTERS, criterion="maxclust")

    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(cluster_labels):
        clusters.setdefault(int(label), []).append(idx)

    return clusters


# ---------------------------------------------------------------------------
# Archetype proposal
# ---------------------------------------------------------------------------

def propose_archetypes(
    clusters: dict[int, list[int]],
    cib: dict,
    cib_matrix: np.ndarray,
    cib_driver_ids: list[str],
    cib_drivers_list: list[TechDriver | None],
) -> list[dict]:
    """LLM archetype proposal from cluster data. From NB06 Cell 2.

    Returns list of archetype dicts from the LLM.
    """
    n_cib = cib_matrix.shape[0]

    # Build cluster description text
    cluster_descriptions = []
    print(f"=== CIB-Based Driver Clusters ({N_CLUSTERS} clusters) ===\n")
    for cid, indices in sorted(clusters.items()):
        names = [
            cib_drivers_list[i].name[:50]
            for i in indices
            if cib_drivers_list[i]
        ]
        avg_influence = np.mean(
            [cib["influence"].get(cib_driver_ids[i], 0) for i in indices]
        )
        avg_dependence = np.mean(
            [cib["dependence"].get(cib_driver_ids[i], 0) for i in indices]
        )
        print(f"Cluster {cid} (avg influence: {avg_influence:+.1f}, avg dependence: {avg_dependence:+.1f}):")
        for name in names:
            print(f"  - {name}")
        cluster_descriptions.append(
            f"Cluster {cid} (influence={avg_influence:+.1f}, dependence={avg_dependence:+.1f}): "
            f"{', '.join(names)}"
        )
        print()

    # Identify tensions (pairs with score <= -1)
    tension_pairs = []
    for i in range(n_cib):
        for j in range(n_cib):
            if i != j and cib_matrix[i][j] <= -1:
                tension_pairs.append(
                    f"{cib_drivers_list[i].name[:40]} -> "
                    f"{cib_drivers_list[j].name[:40]}: {cib_matrix[i][j]}"
                )

    # Influence ranking text
    influence_ranking = sorted(
        [
            (cib_drivers_list[i].name, cib["influence"].get(cib_driver_ids[i], 0))
            for i in range(n_cib)
        ],
        key=lambda x: x[1],
        reverse=True,
    )
    influence_text = "\n".join(
        [f"  {name[:50]}: influence={score:+d}" for name, score in influence_ranking]
    )

    print(f"Tensions (score <= -1): {len(tension_pairs)}")
    for tp in tension_pairs[:15]:
        print(f"  {tp}")
    if len(tension_pairs) > 15:
        print(f"  ... and {len(tension_pairs) - 15} more")

    tension_text = (
        "\n".join(tension_pairs[:20])
        if tension_pairs
        else "No strong tensions found. Consider mild resource competition between clusters."
    )

    archetype_prompt = ARCHETYPE_PROMPT_TEMPLATE.format(
        n_cib=n_cib,
        cluster_descriptions="\n".join(cluster_descriptions),
        influence_text=influence_text,
        tension_text=tension_text,
    )

    archetype_result = safe_chat_json(
        archetype_prompt,
        system=(
            "You are a technology foresight expert designing diverse scenario archetypes "
            "from cross-impact data. You value intellectual honesty and explore futures "
            "that are uncomfortable, not just optimistic."
        ),
        temperature=0.4,
    )

    return archetype_result.get("archetypes", [])


def _build_scenario_configs(
    archetypes: list[dict],
    clusters: dict[int, list[int]],
    cib: dict,
    cib_driver_ids: list[str],
    cib_drivers_list: list[TechDriver | None],
) -> list[dict]:
    """Convert LLM archetypes into scenario configs with driver state assignments.

    From NB06 Cell 2 (the scenario_configs loop).
    """
    scenario_configs = []

    print(f"\n=== LLM Proposed {len(archetypes)} Scenario Archetypes ===\n")

    for arch in archetypes:
        cluster_states = arch["cluster_states"]
        scenario_drivers: list[TechDriver] = []
        driver_states: dict[str, str] = {}

        for cid_str, state in cluster_states.items():
            cid = int(cid_str)
            for idx in clusters.get(cid, []):
                d = cib_drivers_list[idx]
                if d:
                    scenario_drivers.append(d)
                    driver_states[d.id] = state

        stype_str = arch.get("scenario_type", "evolutionary")
        stype = (
            ScenarioType(stype_str)
            if stype_str in [e.value for e in ScenarioType]
            else ScenarioType.EVOLUTIONARY
        )

        # Within-cluster state variance for cautionary/wildcard
        if stype in (ScenarioType.CAUTIONARY, ScenarioType.WILDCARD):
            for cid_str, state in cluster_states.items():
                cid = int(cid_str)
                if state == "breakthrough" and len(clusters.get(cid, [])) > 1:
                    cluster_driver_influence = [
                        (idx, cib["influence"].get(cib_driver_ids[idx], 0))
                        for idx in clusters[cid]
                    ]
                    cluster_driver_influence.sort(key=lambda x: x[1], reverse=True)
                    for rank, (idx, _) in enumerate(cluster_driver_influence):
                        d = cib_drivers_list[idx]
                        if d and rank > 0:
                            driver_states[d.id] = "steady_progress"

        state_counts: dict[str, int] = {}
        for s in driver_states.values():
            state_counts[s] = state_counts.get(s, 0) + 1

        print(f"  [{stype.value:14s}] {arch['short_name']}")
        print(f"    Perspective: {arch.get('perspective', '')}")
        print(f"    States: {state_counts}")
        print(f"    Rationale: {arch.get('rationale', '')[:120]}...")
        print()

        scenario_configs.append({
            "name": arch["short_name"],
            "type": stype,
            "perspective": arch.get("perspective", ""),
            "drivers": scenario_drivers,
            "states": driver_states,
            "rationale": arch.get("rationale", ""),
            "cluster_states": cluster_states,
        })

    print(f"Will generate {len(scenario_configs)} scenarios")
    return scenario_configs


# ---------------------------------------------------------------------------
# CIB Consistency Check
# ---------------------------------------------------------------------------

def check_cib_consistency(
    driver_ids: list[str],
    states: list[str],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    driver_by_id: dict[str, TechDriver],
    threshold: int = -1,
) -> tuple[list[str], list[str]]:
    """Check and fix contradictions. From NB06 Cell 4.

    If A='breakthrough' and CIB[A->B] <= threshold, B can't be 'breakthrough'
    -- downgrade to 'steady_progress'.

    Returns (adjusted_states, adjustment_log).
    """
    adjusted = list(states)
    adjustments = []

    for i, (did_a, state_a) in enumerate(zip(driver_ids, adjusted)):
        if state_a != "breakthrough":
            continue
        idx_a = cib_id_to_idx.get(did_a)
        if idx_a is None:
            continue

        for j, (did_b, state_b) in enumerate(zip(driver_ids, adjusted)):
            if i == j or state_b != "breakthrough":
                continue
            idx_b = cib_id_to_idx.get(did_b)
            if idx_b is None:
                continue

            score = int(cib_matrix[idx_a][idx_b])
            if score <= threshold:
                adjusted[j] = "steady_progress"
                da = driver_by_id.get(did_a)
                db = driver_by_id.get(did_b)
                adjustments.append(
                    f"  CIB[{da.name[:30] if da else did_a} -> "
                    f"{db.name[:30] if db else did_b}] = {score}: "
                    f"downgraded '{db.name[:30] if db else did_b}' to steady_progress"
                )

    return adjusted, adjustments


# ---------------------------------------------------------------------------
# Scenario Generation
# ---------------------------------------------------------------------------

def generate_scenarios(
    scenario_configs: list[dict],
    drivers: list[TechDriver],
    cib: dict,
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    driver_by_id: dict[str, TechDriver],
    collection,
) -> list[Scenario]:
    """Generate scenario narratives via LLM. From NB06 Cell 5.

    This is the main scenario generation loop: builds DriverAssumption objects,
    constructs CIB context, performs state-aware RAG retrieval with chunk
    novelty tracking, calls SCENARIO_GENERATE prompt, and creates Scenario
    objects.
    """
    cib_driver_ids = cib["driver_ids"]
    scenarios: list[Scenario] = []
    generated_titles: list[str] = []
    used_chunk_ids: set[str] = set()

    for config in scenario_configs:
        print(f"\n{'=' * 60}")
        print(f"Generating: {config['name']} [{config['type'].value}]")
        print(f"Perspective: {config.get('perspective', '')}")
        print(f"{'=' * 60}")

        adjusted_states = config["adjusted_states"]

        # Build DriverAssumption objects
        assumptions = []
        for i, d in enumerate(config["drivers"]):
            state = adjusted_states[i]
            assumptions.append(
                DriverAssumption(
                    driver_id=d.id,
                    state=state,
                    description=f"{d.name}: {state}",
                )
            )

        assumptions_text = "\n".join(
            [
                f"- {a.description} (Driver origin: "
                f"{next((d.origin.value for d in drivers if d.id == a.driver_id), '?')})"
                for a in assumptions
            ]
        )

        # CIB context -- include |score| >= 1 for richer context
        cib_context_parts = []
        scenario_driver_ids = [d.id for d in config["drivers"]]
        for did_a in scenario_driver_ids:
            idx_a = cib_id_to_idx.get(did_a)
            if idx_a is None:
                continue
            da = driver_by_id.get(did_a)
            for did_b in scenario_driver_ids:
                if did_a == did_b:
                    continue
                idx_b = cib_id_to_idx.get(did_b)
                if idx_b is None:
                    continue
                score = int(cib_matrix[idx_a][idx_b])
                if abs(score) >= 1:
                    db = driver_by_id.get(did_b)
                    if score >= 2:
                        effect = "strongly promotes"
                    elif score == 1:
                        effect = "mildly promotes"
                    elif score == -1:
                        effect = "mildly inhibits"
                    else:
                        effect = "strongly inhibits"
                    cib_context_parts.append(
                        f"- {da.name[:40]} {effect} {db.name[:40]} (score: {score:+d})"
                    )
        cib_context = (
            "\n".join(cib_context_parts)
            if cib_context_parts
            else "No notable cross-impacts among this scenario's drivers."
        )

        existing_titles_block = ""
        if generated_titles:
            existing_titles_block = (
                "Previously generated scenario titles (yours must be clearly distinct):\n"
                + "\n".join(f"- {t}" for t in generated_titles)
            )

        # State-aware RAG retrieval
        state_phrases = []
        for i, d in enumerate(config["drivers"]):
            state = adjusted_states[i]
            if state == "breakthrough":
                state_phrases.append(f"{d.name} breakthrough advances")
            elif state == "stagnation":
                state_phrases.append(f"{d.name} challenges barriers limitations")
            else:
                state_phrases.append(f"{d.name} incremental progress")

        perspective = config.get("perspective", "")
        query_text = f"{' '.join(state_phrases[:4])} {perspective} spectrum monitoring 2035"
        query_emb = embed([query_text[:500]])[0]
        rag = collection.query(
            query_embeddings=[query_emb],
            n_results=8,
            include=["documents", "metadatas"],
        )

        # Prefer novel chunks not yet used by previous scenarios
        novel = [
            (rag["ids"][0][i], rag["documents"][0][i], rag["metadatas"][0][i])
            for i in range(len(rag["ids"][0]))
            if rag["ids"][0][i] not in used_chunk_ids
        ]
        reused = [
            (rag["ids"][0][i], rag["documents"][0][i], rag["metadatas"][0][i])
            for i in range(len(rag["ids"][0]))
            if rag["ids"][0][i] in used_chunk_ids
        ]
        ranked = (novel + reused)[:5]

        rag_text = "\n\n---\n\n".join(
            [
                f"[Chunk ID: {cid}] (Source: {meta['source_title']})\n{doc}"
                for cid, doc, meta in ranked
            ]
        )
        rag_chunk_ids = [cid for cid, _, _ in ranked]

        # Get type-specific narrative guide
        narrative_guide = SCENARIO_NARRATIVE_GUIDE.get(
            config["type"].value,
            SCENARIO_NARRATIVE_GUIDE["evolutionary"],
        )

        prompt = SCENARIO_GENERATE.format(
            driver_assumptions=assumptions_text,
            scenario_type=config["type"].value,
            perspective=perspective,
            narrative_guide=narrative_guide,
            existing_titles_block=existing_titles_block,
            cib_context=cib_context,
            rag_chunks=rag_text,
        )

        system = SYSTEM_PROMPTS.get(config["type"].value, SYSTEM_PROMPTS["evolutionary"])
        result = safe_chat_json(prompt, system=system, temperature=0.7)

        # Merge source IDs -- only keep IDs that exist in the RAG results
        all_source_ids = list(rag_chunk_ids)
        all_source_ids.extend(result.get("source_chunk_ids_used", []))
        all_source_ids = list(set(all_source_ids))

        used_chunk_ids.update(rag_chunk_ids)

        scenario = Scenario(
            title=result.get("title", config["name"]),
            narrative=result.get("narrative", ""),
            type=config["type"],
            perspective=perspective,
            key_tensions=result.get("key_tensions", []),
            assumptions=assumptions,
            source_chunk_ids=all_source_ids,
        )
        scenarios.append(scenario)
        generated_titles.append(scenario.title)

        print(f"\nTitle: {scenario.title}")
        print(f"Narrative preview: {scenario.narrative[:300]}...")
        print(f"Key tensions: {scenario.key_tensions}")
        print(f"Key changes: {result.get('key_changes', [])}")
        print(f"Source chunks: {len(scenario.source_chunk_ids)}")

    # Diversity check
    print(f"\n=== Generated {len(scenarios)} scenarios ===")
    print(f"\nDiversity check:")
    for s in scenarios:
        state_counts: dict[str, int] = {}
        for a in s.assumptions:
            state_counts[a.state] = state_counts.get(a.state, 0) + 1
        has_mixed = len(state_counts) >= 2
        mark = "OK" if has_mixed else "WARN"
        print(f"  [{mark}] [{s.type.value:14s}] {s.title[:50]} -- {state_counts}")

    # Chunk overlap check
    print(f"\nChunk overlap:")
    all_chunks = [set(s.source_chunk_ids) for s in scenarios]
    for i in range(len(all_chunks)):
        for j in range(i + 1, len(all_chunks)):
            overlap = len(all_chunks[i] & all_chunks[j])
            total = len(all_chunks[i] | all_chunks[j])
            pct = overlap / total * 100 if total else 0
            flag = " WARNING" if pct > 50 else ""
            print(f"  S{i + 1} vs S{j + 1}: {pct:.0f}%{flag}")

    return scenarios


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    output_path: str = "data/outputs/scenario_state.json",
) -> dict:
    """Run full scenario generation pipeline.

    1. Load drivers and CIB state
    2. Cluster drivers via hierarchical clustering on CIB profiles
    3. Propose scenario archetypes via LLM
    4. Apply CIB consistency checks
    5. Generate scenario narratives via LLM + RAG
    6. Save results
    """
    collection = get_collection()

    # Load data
    with open(merge_state_path) as f:
        drivers = [TechDriver(**d) for d in json.load(f)["unified_drivers"]]

    with open(cib_state_path) as f:
        cib = json.load(f)

    cib_matrix = np.array(cib["matrix"])
    cib_driver_ids = cib["driver_ids"]
    cib_id_to_idx = {did: i for i, did in enumerate(cib_driver_ids)}
    driver_by_id = {d.id: d for d in drivers}

    print(f"Drivers: {len(drivers)}")
    print(f"CIB matrix: {cib_matrix.shape}")

    # Step 1: Cluster drivers
    clusters = cluster_drivers(cib_matrix)

    cib_drivers_list: list[TechDriver | None] = [
        driver_by_id.get(did) for did in cib_driver_ids
    ]

    # Step 2: Propose archetypes
    archetypes = propose_archetypes(
        clusters, cib, cib_matrix, cib_driver_ids, cib_drivers_list
    )

    # Step 3: Build scenario configs
    scenario_configs = _build_scenario_configs(
        archetypes, clusters, cib, cib_driver_ids, cib_drivers_list
    )

    # Step 4: CIB consistency check
    print("\n=== CIB Consistency Check ===\n")
    for config in scenario_configs:
        d_ids = [d.id for d in config["drivers"]]
        states = [config["states"][d.id] for d in config["drivers"]]

        adjusted_states, adj_log = check_cib_consistency(
            d_ids, states, cib_matrix, cib_id_to_idx, driver_by_id
        )

        if adj_log:
            print(f"[{config['name']}] -- {len(adj_log)} adjustment(s):")
            for line in adj_log:
                print(line)
        else:
            print(f"[{config['name']}] -- consistent")

        config["adjusted_states"] = adjusted_states

    # Step 5: Generate scenarios
    scenarios = generate_scenarios(
        scenario_configs,
        drivers,
        cib,
        cib_matrix,
        cib_id_to_idx,
        driver_by_id,
        collection,
    )

    # Step 6: Save
    state = {
        "scenarios": [s.model_dump(mode="json") for s in scenarios],
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nSaved {len(scenarios)} scenarios")
    return state
