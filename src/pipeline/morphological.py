"""Morphological analysis: CIB-consistent scenario generation.

Implements the Weimer-Jehle balance algorithm adapted to driver-to-driver CIB:
manifestation ordering (optimistic→pessimistic) + CIB influence scores determine
which manifestation each driver "settles" into given the others' states.
"""

from __future__ import annotations

import logging
import random
from collections import Counter

import numpy as np

from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)

log = logging.getLogger(__name__)

_OPTIMISTIC_ANCHOR = (
    "positive improvement success advancement enabling progress "
    "breakthrough growth opportunity benefit"
)
_PESSIMISTIC_ANCHOR = (
    "negative decline failure stagnation regression barrier "
    "disruption risk fragmentation constraint"
)


def validate_manifestation_ordering(
    manifestations: list[DriverManifestation],
    driver_name: str = "",
) -> list[float]:
    """Verify that manifestations are ordered optimistic→pessimistic using embeddings.

    Returns the optimism scores. Raises ValueError if ordering is violated.
    """
    from src.llm import embed

    if len(manifestations) <= 1:
        return [0.5] * len(manifestations)

    texts = [f"{m.label}: {m.description}" for m in manifestations]
    all_texts = texts + [_OPTIMISTIC_ANCHOR, _PESSIMISTIC_ANCHOR]
    embeddings = embed(all_texts)

    manif_vecs = np.array(embeddings[: len(texts)])
    opt_vec = np.array(embeddings[-2])
    pes_vec = np.array(embeddings[-1])

    opt_vec = opt_vec / np.linalg.norm(opt_vec)
    pes_vec = pes_vec / np.linalg.norm(pes_vec)
    norms = np.linalg.norm(manif_vecs, axis=1, keepdims=True)
    manif_vecs = manif_vecs / norms

    opt_sims = manif_vecs @ opt_vec
    pes_sims = manif_vecs @ pes_vec
    optimism_scores = (opt_sims - pes_sims).tolist()

    violations = []
    for i in range(len(optimism_scores) - 1):
        if optimism_scores[i] < optimism_scores[i + 1] - 0.02:
            violations.append(
                f"  [{i}] {manifestations[i].label} (optimism={optimism_scores[i]:.3f}) "
                f"< [{i+1}] {manifestations[i+1].label} (optimism={optimism_scores[i+1]:.3f})"
            )

    if violations:
        name = driver_name or manifestations[0].driver_id
        log.warning(
            "Manifestation ordering violated for driver '%s' — auto-reordering.\n%s",
            name, "\n".join(violations),
        )
        return None  # signal to caller that reordering is needed

    return optimism_scores


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
    rng: random.Random | None = None,
) -> dict[str, str]:
    """Iterate through drivers, switching each to best-supported manifestation.

    When *rng* is provided the driver processing order is shuffled each
    iteration, removing the deterministic-order bias that would otherwise
    favour early-listed drivers.
    """
    config = dict(config)
    drivers = list(morph_box.drivers)
    for _ in range(max_iter):
        if rng:
            rng.shuffle(drivers)
        changed = False
        for driver_id in drivers:
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
    """Random-restart hill-climbing to find all unique fixed points.

    INVARIANT: manifestations[driver_id] must be ordered optimistic→pessimistic.
    The support_score function derives direction from position (index 0 = best case,
    index -1 = worst case). Violated ordering causes hill-climbing to converge toward
    wrong fixed points without any error. This ordering is enforced by the BOM
    decomposition prompt — verify there if results look inverted.
    """
    rng = random.Random(seed)
    seen: set[tuple[str, ...]] = set()
    results: list[ConsistencyResult] = []

    for _ in range(n_restarts):
        config = {
            d: rng.choice(morph_box.manifestations[d]) for d in morph_box.drivers
        }
        config = iterate_to_fixed_point(
            config, morph_box, cib_matrix, driver_index, rng=rng,
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
    """Select diverse, high-scoring configurations as scenario seeds.

    When Monte Carlo frequency counts are available (panel mode), configs are
    pre-sorted by frequency so that robust attractors (high basin volume) are
    preferred over fragile fixed points. Frequency = 1 for all configs when
    deterministic mode is used, so the sort is stable in both cases.
    """
    if not configs:
        return []

    # Frequency-first: robust attractors before fragile ones.
    # Secondary sort by consistency_score keeps deterministic mode stable.
    configs = sorted(configs, key=lambda r: (r.frequency, r.consistency_score), reverse=True)

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


def select_scenario_seeds_typed(
    configs: list[ConsistencyResult],
    morph_box: MorphologicalBox,
    n: int = 5,
    min_hamming: int = 3,
) -> list[ConsistencyResult]:
    """Select diverse seeds ensuring at least one of each scenario type.

    Within each type, robust attractors (high MC frequency) are preferred.
    """
    if not configs:
        return []

    # Frequency-first within each type bucket.
    configs = sorted(configs, key=lambda r: (r.frequency, r.consistency_score), reverse=True)

    target_types = ["evolutionary", "disruptive", "cautionary", "wildcard"]
    by_type: dict[str, list[ConsistencyResult]] = {t: [] for t in target_types}
    for c in configs:
        by_type.setdefault(c.scenario_type, []).append(c)

    selected: list[ConsistencyResult] = []

    def _is_diverse(candidate: ConsistencyResult) -> bool:
        return all(
            _hamming_distance(candidate.configuration, s.configuration) >= min_hamming
            for s in selected
        )

    for stype in target_types:
        if len(selected) >= n:
            break
        for candidate in by_type.get(stype, []):
            if _is_diverse(candidate):
                selected.append(candidate)
                break

    for candidate in configs:
        if len(selected) >= n:
            break
        if candidate in selected:
            continue
        if _is_diverse(candidate):
            selected.append(candidate)

    if len(selected) < n:
        for candidate in configs:
            if len(selected) >= n:
                break
            if candidate not in selected:
                selected.append(candidate)

    return selected[:n]


def find_consistent_configs_monte_carlo(
    morph_box: MorphologicalBox,
    persona_scores_map: dict[str, list[int]],
    driver_index: dict[str, int],
    n_mc_samples: int = 200,
    n_restarts_per_sample: int = 100,
    seed: int | None = None,
) -> list[ConsistencyResult]:
    """Monte Carlo sampling over persona score distributions.

    For each MC sample, draw one score per cell from the persona scores,
    build a CIB matrix, and find fixed points. Collects all unique configs
    across samples with frequency counts.
    """
    rng = random.Random(seed)
    n = len(morph_box.drivers)
    freq: dict[tuple[str, ...], int] = Counter()
    config_store: dict[tuple[str, ...], dict[str, str]] = {}
    score_sum: dict[tuple[str, ...], float] = {}  # accumulate for mean

    for _ in range(n_mc_samples):
        sampled_matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                key = f"{i},{j}"
                scores = persona_scores_map.get(key, [0])
                sampled_matrix[i][j] = rng.choice(scores)

        configs = find_consistent_configs(
            morph_box, sampled_matrix, driver_index,
            n_restarts=n_restarts_per_sample, seed=rng.randint(0, 2**31),
        )
        for c in configs:
            ckey = _config_key(c.configuration, morph_box)
            freq[ckey] += 1
            if ckey not in config_store:
                config_store[ckey] = c.configuration
                score_sum[ckey] = 0.0
            score_sum[ckey] += c.consistency_score

    results = []
    for ckey, count in freq.most_common():
        results.append(ConsistencyResult(
            configuration=config_store[ckey],
            consistency_score=round(score_sum[ckey] / count, 3),  # mean across MC samples
            is_consistent=True,
            frequency=count,
        ))

    return results


def find_near_consistent_neighbors(
    fixed_points: list[ConsistencyResult],
    morph_box: MorphologicalBox,
    cib_matrix: list[list[int]],
    driver_index: dict[str, int],
) -> list[ConsistencyResult]:
    """Single-driver-flip neighbors of each fixed point, scored by consistency."""
    seen: set[tuple[str, ...]] = set()
    fp_keys: set[tuple[str, ...]] = set()
    for fp in fixed_points:
        fp_keys.add(_config_key(fp.configuration, morph_box))

    results: list[ConsistencyResult] = []
    for fp in fixed_points:
        for driver_id in morph_box.drivers:
            original_manif = fp.configuration[driver_id]
            for alt_manif in morph_box.manifestations[driver_id]:
                if alt_manif == original_manif:
                    continue
                neighbor = dict(fp.configuration)
                neighbor[driver_id] = alt_manif
                key = _config_key(neighbor, morph_box)
                if key in seen or key in fp_keys:
                    continue
                seen.add(key)
                score = _total_consistency(neighbor, morph_box, cib_matrix, driver_index)
                results.append(ConsistencyResult(
                    configuration=neighbor,
                    consistency_score=score,
                    is_consistent=False,
                    is_fixed_point=False,
                    parent_fixed_point_id=fp.id,
                    flipped_driver_id=driver_id,
                ))
    results.sort(key=lambda r: r.consistency_score, reverse=True)
    return results


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
    # Use 1/3 boundaries so that with 4 manifestations (positions 0.0, 0.333, 0.667, 1.0)
    # the two inner positions land in neither "clearly optimistic" nor "clearly pessimistic".
    optimistic = sum(1 for p in positions if p <= 1/3)   # lower third: clearly good
    pessimistic = sum(1 for p in positions if p >= 2/3)  # upper third: clearly bad

    if pessimistic >= n * 0.6:
        return "cautionary"
    if optimistic >= n * 0.6:
        return "disruptive"
    # Wildcard: both extremes are meaningfully present — polarised, no consensus
    if optimistic >= n * 0.25 and pessimistic >= n * 0.25:
        return "wildcard"
    return "evolutionary"  # balanced / moderate — neither pole dominates
