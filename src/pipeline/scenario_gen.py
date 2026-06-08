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

import itertools
import json
import logging
import os
from collections import Counter

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
CLUSTER_STATES = ("breakthrough", "steady_progress", "stagnation")

logger = logging.getLogger(__name__)

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
# Combinatorial cluster-state search
# ---------------------------------------------------------------------------

def enumerate_cluster_state_combos(
    clusters: dict[int, list[int]],
) -> list[dict[int, str]]:
    """All cluster-level state assignments via Cartesian product of CLUSTER_STATES."""
    cluster_ids = sorted(clusters.keys())
    return [
        dict(zip(cluster_ids, states))
        for states in itertools.product(CLUSTER_STATES, repeat=len(cluster_ids))
    ]


def _combo_to_driver_states(
    combo: dict[int, str],
    clusters: dict[int, list[int]],
    cib_driver_ids: list[str],
) -> dict[str, str]:
    """Expand cluster states to per-driver states for CIB matrix drivers."""
    driver_states: dict[str, str] = {}
    for cid, indices in clusters.items():
        state = combo[cid]
        for idx in indices:
            driver_states[cib_driver_ids[idx]] = state
    return driver_states


def score_combo_consistency(
    combo: dict[int, str],
    clusters: dict[int, list[int]],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    cib_driver_ids: list[str],
    threshold: int = 1,
) -> float:
    """Weighted conflict score for a cluster-state combo (lower is better).

    Penalties mirror :func:`_cib_rule_specs` but as floats:
    - breakthrough_inhibits / stagnation_promotes: ``abs(score)``
    - steady_progress_inhibits: ``abs(score) * 0.5``
    """
    driver_states = _combo_to_driver_states(combo, clusters, cib_driver_ids)
    penalty = 0.0

    for did_a, state_a in driver_states.items():
        idx_a = cib_id_to_idx.get(did_a)
        if idx_a is None:
            continue
        for did_b, state_b in driver_states.items():
            if did_a == did_b or state_b != "breakthrough":
                continue
            idx_b = cib_id_to_idx.get(did_b)
            if idx_b is None:
                continue

            score = int(cib_matrix[idx_a][idx_b])
            if state_a == "breakthrough" and score <= -threshold:
                penalty += abs(score)
            elif state_a == "stagnation" and score >= threshold:
                penalty += abs(score)
            elif state_a == "steady_progress" and score <= -threshold:
                penalty += abs(score) * 0.5

    return penalty


def select_top_combos(
    clusters: dict[int, list[int]],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    cib_driver_ids: list[str],
    top_k: int = 5,
    threshold: int = 1,
    alpha: float = 0.5,
    propagation_threshold: int | None = None,
    max_iterations: int = 10,
) -> list[tuple[dict[int, str], float, int, float]]:
    """Score all combos, take top K by base score, re-rank after propagation.

    First pass: sort by :func:`score_combo_consistency` (ascending). Then run
    :func:`propagate_cib_consistency` on each of the top K and re-rank by
    ``final_score = base_score + alpha * correction_count`` (lower is better).

    Returns list of ``(combo, base_score, correction_count, final_score)``.
    When ``alpha=0``, propagation is skipped and base-score order is preserved.
    """
    prop_threshold = threshold if propagation_threshold is None else propagation_threshold
    combos = enumerate_cluster_state_combos(clusters)
    scored = [
        (
            combo,
            score_combo_consistency(
                combo,
                clusters,
                cib_matrix,
                cib_id_to_idx,
                cib_driver_ids,
                threshold=threshold,
            ),
        )
        for combo in combos
    ]
    scored.sort(key=lambda item: item[1])
    top = scored[:top_k]

    if alpha == 0:
        return [(combo, base, 0, base) for combo, base in top]

    return rerank_combos(
        top,
        clusters,
        cib_matrix,
        cib_id_to_idx,
        cib_driver_ids,
        alpha=alpha,
        threshold=prop_threshold,
        max_iterations=max_iterations,
    )


def rerank_combos(
    scored: list[tuple[dict[int, str], float]],
    clusters: dict[int, list[int]],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    cib_driver_ids: list[str],
    alpha: float = 0.5,
    threshold: int = 1,
    max_iterations: int = 10,
) -> list[tuple[dict[int, str], float, int, float]]:
    """Re-rank combos using propagation correction counts.

    ``final_score = base_score + alpha * correction_count`` (lower is better).
    Does not change which combos are in the list — only their order.
    """
    reranked: list[tuple[dict[int, str], float, int, float]] = []

    for combo, base_score in scored:
        if alpha == 0:
            correction_count = 0
        else:
            initial_states = _combo_to_driver_states(combo, clusters, cib_driver_ids)
            _, corrections, _ = propagate_cib_consistency(
                initial_states,
                cib_matrix,
                cib_id_to_idx,
                threshold=threshold,
                max_iterations=max_iterations,
            )
            correction_count = len(corrections)
        final_score = base_score + alpha * correction_count
        reranked.append((combo, base_score, correction_count, final_score))

    reranked.sort(key=lambda item: (item[3], item[2], item[1]))
    return reranked


def build_combinatorial_meta(
    clusters: dict[int, list[int]],
    top_combos: list[tuple[dict[int, str], float, int, float]],
    top_k: int,
    threshold: int,
    alpha: float,
) -> dict:
    """Summary of combinatorial cluster-state search for JSON output."""
    n_clusters = len(clusters)
    total_combos = 3**n_clusters if n_clusters else 0
    return {
        "cluster_count": n_clusters,
        "total_combos_enumerated": total_combos,
        "top_k": top_k,
        "threshold": threshold,
        "alpha": alpha,
        "top_combos": [
            {
                "cluster_states": {str(cid): state for cid, state in combo.items()},
                "base_score": base_score,
                "correction_count": correction_count,
                "final_score": final_score,
            }
            for combo, base_score, correction_count, final_score in top_combos
        ],
    }


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

def _cib_rule_specs(threshold: int) -> list[dict]:
    """Rule definitions in application order.

    Each spec: source_state, rule, predicate, target_state (required B state),
    new_state (B becomes this when the rule fires).
    """
    return [
        {
            "source_state": "breakthrough",
            "rule": "breakthrough_inhibits",
            "predicate": lambda score: score <= -threshold,
            "target_state": "breakthrough",
            "new_state": "steady_progress",
        },
        {
            "source_state": "stagnation",
            "rule": "stagnation_promotes",
            "predicate": lambda score: score >= threshold,
            "target_state": "breakthrough",
            "new_state": "steady_progress",
        },
        {
            "source_state": "steady_progress",
            "rule": "steady_progress_inhibits",
            "predicate": lambda score: score <= -threshold,
            "target_state": "breakthrough",
            "new_state": "steady_progress",
        },
        {
            "source_state": "breakthrough",
            "rule": "breakthrough_lifts",
            "predicate": lambda score: score >= threshold,
            "target_state": "stagnation",
            "new_state": "steady_progress",
        },
    ]


def _apply_cib_rule(
    driver_ids: list[str],
    states: list[str],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    source_state: str,
    rule: str,
    predicate,
    target_state: str,
    new_state: str,
) -> tuple[list[str], list[dict]]:
    """Apply a single consistency rule; returns (adjusted_states, corrections)."""
    adjusted = list(states)
    corrections: list[dict] = []

    for i, did_a in enumerate(driver_ids):
        if adjusted[i] != source_state:
            continue
        idx_a = cib_id_to_idx.get(did_a)
        if idx_a is None:
            continue

        for j, did_b in enumerate(driver_ids):
            if i == j or adjusted[j] != target_state:
                continue
            idx_b = cib_id_to_idx.get(did_b)
            if idx_b is None:
                continue

            score = int(cib_matrix[idx_a][idx_b])
            if not predicate(score):
                continue

            old_state = adjusted[j]
            adjusted[j] = new_state
            corrections.append({
                "trigger_driver_id": did_a,
                "corrected_driver_id": did_b,
                "trigger_state": source_state,
                "rule": rule,
                "score": score,
                "old_state": old_state,
                "new_state": new_state,
            })

    return adjusted, corrections


def check_cib_consistency(
    driver_ids: list[str],
    states: list[str],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    threshold: int = 1,
) -> tuple[list[str], list[dict]]:
    """Check and fix contradictions. From NB06 Cell 4.

    Rules (applied in order; each pass uses current adjusted states):
    1. breakthrough_inhibits: A='breakthrough', CIB[A->B] <= -threshold, B='breakthrough'
       -> downgrade B to 'steady_progress'.
    2. stagnation_promotes: A='stagnation', CIB[A->B] >= threshold, B='breakthrough'
       -> downgrade B to 'steady_progress'.
    3. steady_progress_inhibits: A='steady_progress', CIB[A->B] <= -threshold, B='breakthrough'
       -> downgrade B to 'steady_progress'.
    4. breakthrough_lifts: A='breakthrough', CIB[A->B] >= threshold, B='stagnation'
       -> upgrade B to 'steady_progress'.

    With default threshold=1, rules 1 and 3 trigger at score <= -1; rules 2 and 4 at score >= 1.
    Rules 3–4 enable bidirectional cascade fixes across :func:`propagate_cib_consistency`.

    Each correction dict: trigger_driver_id, corrected_driver_id, trigger_state,
    rule, score, old_state, new_state.

    Returns (adjusted_states, corrections).
    """
    adjusted = list(states)
    corrections: list[dict] = []

    for spec in _cib_rule_specs(threshold):
        adjusted, rule_corrections = _apply_cib_rule(
            driver_ids,
            adjusted,
            cib_matrix,
            cib_id_to_idx,
            spec["source_state"],
            spec["rule"],
            spec["predicate"],
            spec["target_state"],
            spec["new_state"],
        )
        corrections.extend(rule_corrections)

    return adjusted, corrections


def propagate_cib_consistency(
    initial_states: dict[str, str],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    threshold: int = 1,
    max_iterations: int = 10,
) -> tuple[dict[str, str], list[dict], int]:
    """Apply CIB consistency checks until a fixed point or ``max_iterations``.

    **First-match semantics.** Each iteration walks :func:`_cib_rule_specs` in
    order and applies the first rule that produces at least one correction,
    then ends that pass—later rules wait until the next iteration. For a given
    pair (A→B), only one rule can fire per pass; if several rules could match
    the same pair, the earliest in the list wins and the rest are skipped for
    that pair in that pass.

    **Rule order** (position in ``_cib_rule_specs`` = priority):

    1. ``breakthrough_inhibits`` — A breakthrough, B breakthrough, score ≤ −threshold → downgrade B
    2. ``stagnation_promotes`` — A stagnation, B breakthrough, score ≥ +threshold → downgrade B
    3. ``steady_progress_inhibits`` — A steady_progress, B breakthrough, score ≤ −threshold → downgrade B
    4. ``breakthrough_lifts`` — A breakthrough, B stagnation, score ≥ +threshold → upgrade B

    Order matters: downgrades are checked before ``breakthrough_lifts``, so a
    breakthrough source with both a negative link to a breakthrough neighbour
    and a positive link to a stagnating one resolves via whichever rule fires
    first on that pass (usually only one ``target_state`` matches B at a time).
    Cascades across passes (e.g. lift then ``steady_progress_inhibits``) rely
    on state changes between iterations.

    **Adding rules:** choose insertion position deliberately—more specific or
    stronger constraints should precede broader ones; list order is priority.

    Correction entries include ``iteration`` (1-based pass) and ``propagated``
    (``True`` when ``iteration > 1``).

    Returns ``(final_states, all_corrections, iterations_run)``.
    """
    driver_ids = list(initial_states.keys())
    current_states = dict(initial_states)
    all_corrections: list[dict] = []
    iterations_run = 0

    for iteration in range(1, max_iterations + 1):
        state_list = [current_states[did] for did in driver_ids]
        iteration_corrections: list[dict] = []

        for spec in _cib_rule_specs(threshold):
            adjusted_list, rule_corrections = _apply_cib_rule(
                driver_ids,
                state_list,
                cib_matrix,
                cib_id_to_idx,
                spec["source_state"],
                spec["rule"],
                spec["predicate"],
                spec["target_state"],
                spec["new_state"],
            )
            if rule_corrections:
                state_list = adjusted_list
                iteration_corrections = rule_corrections
                break

        for c in iteration_corrections:
            all_corrections.append({
                **c,
                "iteration": iteration,
                "propagated": iteration > 1,
            })

        current_states = {
            did: state for did, state in zip(driver_ids, state_list)
        }
        iterations_run = iteration

        if not iteration_corrections:
            break

    return current_states, all_corrections, iterations_run


def apply_cib_consistency_to_configs(
    scenario_configs: list[dict],
    cib_matrix: np.ndarray,
    cib_id_to_idx: dict[str, int],
    threshold: int = 1,
    max_iterations: int = 10,
) -> tuple[list[dict], list[dict], dict]:
    """Run propagated CIB consistency checks on all scenario configs.

    Mutates each config with ``adjusted_states``, ``cib_corrections``, and
    ``cib_consistency_iterations``. Returns (scenario_configs, all_corrections,
    per_scenario_meta) where each correction includes ``scenario``.
    """
    all_corrections: list[dict] = []
    per_scenario_meta: dict[str, dict] = {}

    for config in scenario_configs:
        initial_states = {d.id: config["states"][d.id] for d in config["drivers"]}
        driver_ids = [d.id for d in config["drivers"]]

        final_states, corrections, iterations_run = propagate_cib_consistency(
            initial_states,
            cib_matrix,
            cib_id_to_idx,
            threshold=threshold,
            max_iterations=max_iterations,
        )

        config["adjusted_states"] = [final_states[did] for did in driver_ids]
        config["cib_corrections"] = corrections
        config["cib_consistency_iterations"] = iterations_run

        propagated_count = sum(1 for c in corrections if c["propagated"])
        per_scenario_meta[config["name"]] = {
            "iterations_run": iterations_run,
            "correction_count": len(corrections),
            "propagated_count": propagated_count,
        }

        for c in corrections:
            all_corrections.append({"scenario": config["name"], **c})

    return scenario_configs, all_corrections, per_scenario_meta


def build_consistency_meta(
    per_scenario_meta: dict[str, dict],
    all_corrections: list[dict],
    threshold: int,
    max_iterations: int,
) -> dict:
    """Summarize CIB consistency propagation across scenarios."""
    total_propagated = sum(1 for c in all_corrections if c.get("propagated"))
    return {
        "threshold": threshold,
        "max_iterations": max_iterations,
        "by_scenario": per_scenario_meta,
        "total_corrections": len(all_corrections),
        "total_propagated": total_propagated,
        "scenarios_with_corrections": sum(
            1 for m in per_scenario_meta.values() if m["correction_count"] > 0
        ),
    }


def correction_frequency_summary(all_corrections: list[dict]) -> dict:
    """Aggregate correction counts across all scenarios from a full run.

    Surfaces drivers and pairs that are frequently corrected — candidates for
    CIB score re-evaluation rather than repeated scenario-state patching.
    """
    by_corrected = Counter(
        c["corrected_driver_id"] for c in all_corrections if c.get("corrected_driver_id")
    )
    by_pair = Counter(
        f"{c['trigger_driver_id']}->{c['corrected_driver_id']}"
        for c in all_corrections
        if c.get("trigger_driver_id") and c.get("corrected_driver_id")
    )
    by_rule = Counter(c["rule"] for c in all_corrections if c.get("rule"))

    return {
        "by_corrected_driver": dict(by_corrected),
        "by_driver_pair": dict(by_pair),
        "by_rule": dict(by_rule),
    }


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
    cib_consistency_threshold: int = 1,
    cib_consistency_max_iterations: int = 10,
    combinatorial_top_k: int = 5,
    combinatorial_threshold: int = 1,
    combinatorial_alpha: float = 0.5,
) -> dict:
    """Run full scenario generation pipeline.

    1. Load drivers and CIB state
    2. Cluster drivers via hierarchical clustering on CIB profiles
    2b. Enumerate/score cluster-state combos; re-rank top-K after propagation
    3. Propose scenario archetypes via LLM
    4. Apply CIB consistency checks (see ``cib_consistency_threshold``)
    5. Generate scenario narratives via LLM + RAG
    6. Save results (includes flat ``cib_corrections`` list)
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

    if len(clusters) > 10:
        logger.warning(
            "Cluster count %d exceeds 10 — combinatorial search will enumerate "
            "%d combos (3^%d); consider reducing N_CLUSTERS.",
            len(clusters),
            3 ** len(clusters),
            len(clusters),
        )

    top_combos = select_top_combos(
        clusters,
        cib_matrix,
        cib_id_to_idx,
        cib_driver_ids,
        top_k=combinatorial_top_k,
        threshold=combinatorial_threshold,
        alpha=combinatorial_alpha,
        propagation_threshold=cib_consistency_threshold,
        max_iterations=cib_consistency_max_iterations,
    )
    combinatorial_meta = build_combinatorial_meta(
        clusters,
        top_combos,
        combinatorial_top_k,
        combinatorial_threshold,
        combinatorial_alpha,
    )

    print(f"\n=== Combinatorial cluster-state search ===")
    print(
        f"Enumerated {combinatorial_meta['total_combos_enumerated']} combos "
        f"({combinatorial_meta['cluster_count']} clusters), "
        f"top {combinatorial_top_k} after re-rank (alpha={combinatorial_alpha}):"
    )
    for rank, entry in enumerate(combinatorial_meta["top_combos"], start=1):
        print(
            f"  #{rank} final={entry['final_score']:.2f} "
            f"(base={entry['base_score']:.2f}, corrections={entry['correction_count']}) "
            f"states={entry['cluster_states']}"
        )

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
    print(
        f"\n=== CIB Consistency Check "
        f"(threshold={cib_consistency_threshold}, max_iterations={cib_consistency_max_iterations}) ===\n"
    )
    scenario_configs, all_cib_corrections, per_scenario_meta = (
        apply_cib_consistency_to_configs(
            scenario_configs,
            cib_matrix,
            cib_id_to_idx,
            threshold=cib_consistency_threshold,
            max_iterations=cib_consistency_max_iterations,
        )
    )

    consistency_meta = build_consistency_meta(
        per_scenario_meta,
        all_cib_corrections,
        cib_consistency_threshold,
        cib_consistency_max_iterations,
    )
    correction_freq = correction_frequency_summary(all_cib_corrections)

    for config in scenario_configs:
        meta = per_scenario_meta.get(config["name"], {})
        corrections = config.get("cib_corrections", [])
        if corrections:
            print(
                f"[{config['name']}] -- {len(corrections)} adjustment(s), "
                f"{meta.get('iterations_run', '?')} iteration(s):"
            )
            for c in corrections:
                da = driver_by_id.get(c["trigger_driver_id"])
                db = driver_by_id.get(c["corrected_driver_id"])
                prop = " [propagated]" if c.get("propagated") else ""
                print(
                    f"  [iter {c.get('iteration', '?')}{prop}] [{c['rule']}] "
                    f"({c['trigger_state']}) "
                    f"CIB[{da.name[:30] if da else c['trigger_driver_id']} -> "
                    f"{db.name[:30] if db else c['corrected_driver_id']}] = {c['score']}: "
                    f"{c['old_state']} -> {c['new_state']}"
                )
        else:
            print(f"[{config['name']}] -- consistent")

    print(
        f"\nConsistency summary: {consistency_meta['total_corrections']} correction(s) "
        f"({consistency_meta['total_propagated']} propagated) across "
        f"{consistency_meta['scenarios_with_corrections']} scenario(s)"
    )
    if correction_freq["by_corrected_driver"]:
        print(
            f"Correction frequency: {len(correction_freq['by_corrected_driver'])} driver(s), "
            f"{len(correction_freq['by_driver_pair'])} pair(s)"
        )

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
        "cib_corrections": all_cib_corrections,
        "consistency_meta": consistency_meta,
        "correction_frequency_summary": correction_freq,
        "combinatorial_meta": combinatorial_meta,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nSaved {len(scenarios)} scenarios")
    return state
