"""Morphological analysis: CIB-consistent scenario generation.

Implements the Weimer-Jehle balance algorithm adapted to driver-to-driver CIB:
manifestation ordering (optimistic→pessimistic) + CIB influence scores determine
which manifestation each driver "settles" into given the others' states.
"""

from __future__ import annotations

import random
from collections import Counter

from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)


def _manif_index(morph_box: MorphologicalBox, driver_id: str, manif_id: str) -> int:
    return morph_box.manifestations[driver_id].index(manif_id)


def _manif_position(morph_box: MorphologicalBox, driver_id: str, manif_id: str) -> float:
    """Normalized position: 0.0 = most optimistic, 1.0 = most pessimistic."""
    ids = morph_box.manifestations[driver_id]
    n = len(ids)
    if n <= 1:
        return 0.5
    idx = ids.index(manif_id)
    return idx / (n - 1)


def support_score(
    driver_id: str,
    manif_id: str,
    config: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> float:
    """How much the current configuration supports driver_id being in manif_id.

    For each other driver j with CIB score cib[j→k]:
    - Positive CIB + optimistic j → pushes k toward optimistic (low index)
    - Negative CIB + optimistic j → pushes k toward pessimistic (high index)
    The support is highest when the candidate manifestation aligns with these pushes.
    """
    k_pos = _manif_position(morph_box, driver_id, manif_id)
    k_idx = driver_index[driver_id]
    score = 0.0

    for other_id, other_manif in config.items():
        if other_id == driver_id:
            continue
        j_idx = driver_index[other_id]
        cib_val = cib_matrix[j_idx][k_idx]
        if cib_val == 0:
            continue

        j_pos = _manif_position(morph_box, other_id, other_manif)
        optimism_j = 1.0 - j_pos

        if cib_val > 0:
            target_pos = 1.0 - optimism_j
        else:
            target_pos = optimism_j

        distance = abs(k_pos - target_pos)
        score += abs(cib_val) * (1.0 - distance)

    return score


def _best_manifestation(
    driver_id: str,
    config: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> str:
    """Return the manifestation with highest support for driver_id."""
    best_id = config[driver_id]
    best_score = -float("inf")
    for m_id in morph_box.manifestations[driver_id]:
        s = support_score(driver_id, m_id, config, morph_box, cib_matrix, driver_index)
        if s > best_score:
            best_score = s
            best_id = m_id
    return best_id


def iterate_to_fixed_point(
    config: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
    max_iter: int = 100,
) -> dict[str, str]:
    """Iterate through drivers, switching each to best-supported manifestation."""
    config = dict(config)
    for _ in range(max_iter):
        changed = False
        for driver_id in morph_box.drivers:
            best = _best_manifestation(
                driver_id, config, morph_box, cib_matrix, driver_index
            )
            if best != config[driver_id]:
                config[driver_id] = best
                changed = True
        if not changed:
            break
    return config


def is_fixed_point(
    config: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> bool:
    """Check if no single driver switch would improve support."""
    for driver_id in morph_box.drivers:
        best = _best_manifestation(
            driver_id, config, morph_box, cib_matrix, driver_index
        )
        if best != config[driver_id]:
            return False
    return True


def _config_key(config: dict[str, str], morph_box: MorphologicalBox) -> tuple[str, ...]:
    return tuple(config[d] for d in morph_box.drivers)


def _total_consistency(
    config: dict[str, str],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> float:
    return sum(
        support_score(d, config[d], config, morph_box, cib_matrix, driver_index)
        for d in morph_box.drivers
    )


def find_consistent_configs(
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
    n_restarts: int = 5000,
    seed: int | None = None,
) -> list[ConsistencyResult]:
    """Random-restart hill-climbing to find all unique fixed points."""
    rng = random.Random(seed)
    seen: set[tuple[str, ...]] = set()
    results: list[ConsistencyResult] = []

    for _ in range(n_restarts):
        config = {
            d: rng.choice(morph_box.manifestations[d]) for d in morph_box.drivers
        }
        config = iterate_to_fixed_point(
            config, morph_box, cib_matrix, driver_index
        )
        key = _config_key(config, morph_box)
        if key in seen:
            continue
        seen.add(key)

        if is_fixed_point(config, morph_box, cib_matrix, driver_index):
            score = _total_consistency(
                config, morph_box, cib_matrix, driver_index
            )
            results.append(
                ConsistencyResult(
                    configuration=dict(config),
                    consistency_score=score,
                    is_consistent=True,
                )
            )

    results.sort(key=lambda r: r.consistency_score, reverse=True)
    return results


def _hamming_distance(a: dict[str, str], b: dict[str, str]) -> int:
    return sum(1 for k in a if a[k] != b[k])


def select_scenario_seeds(
    configs: list[ConsistencyResult],
    morph_box: MorphologicalBox,
    n: int = 5,
    min_hamming: int = 3,
) -> list[ConsistencyResult]:
    """Select diverse, high-scoring configurations as scenario seeds."""
    if not configs:
        return []

    selected = [configs[0]]
    for candidate in configs[1:]:
        if len(selected) >= n:
            break
        diverse_enough = all(
            _hamming_distance(candidate.configuration, s.configuration) >= min_hamming
            for s in selected
        )
        if diverse_enough:
            selected.append(candidate)

    if len(selected) < n:
        for candidate in configs[1:]:
            if len(selected) >= n:
                break
            if candidate not in selected:
                selected.append(candidate)

    return selected[:n]


def infer_scenario_type(
    config: dict[str, str],
    morph_box: MorphologicalBox,
) -> str:
    """Infer scenario type from the manifestation profile.

    Uses position in the ordered manifestation list:
    index 0 = most optimistic, last = most pessimistic.
    """
    positions = [
        _manif_position(morph_box, d, config[d]) for d in morph_box.drivers
    ]
    n = len(positions)
    optimistic = sum(1 for p in positions if p <= 0.25)
    pessimistic = sum(1 for p in positions if p >= 0.75)

    if pessimistic >= n * 0.6:
        return "cautionary"
    if optimistic >= n * 0.6:
        return "disruptive"
    if optimistic <= n * 0.3 and pessimistic <= n * 0.3:
        return "evolutionary"
    return "wildcard"
