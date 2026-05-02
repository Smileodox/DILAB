"""Cross-Impact Balance algorithm (Weimer-Jehle 2006)."""

import itertools
from typing import Sequence

import numpy as np

from src.models import Driver


def build_state_index(drivers: Sequence[Driver]) -> dict[tuple[str, str], int]:
    idx = {}
    i = 0
    for d in drivers:
        for s in d.states:
            idx[(d.name, s.name)] = i
            i += 1
    return idx


def total_states(drivers: Sequence[Driver]) -> int:
    return sum(len(d.states) for d in drivers)


def compute_impact_sums(
    matrix: np.ndarray,
    scenario: dict[str, str],
    drivers: Sequence[Driver],
    state_index: dict[tuple[str, str], int],
) -> np.ndarray:
    """For each state in the system, sum the influences from all active states in
    the scenario (excluding the state's own driver)."""
    n = total_states(drivers)
    sums = np.zeros(n)

    for driver in drivers:
        active_state = scenario[driver.name]
        src_idx = state_index[(driver.name, active_state)]
        for target_driver in drivers:
            if target_driver.name == driver.name:
                continue
            for ts in target_driver.states:
                tgt_idx = state_index[(target_driver.name, ts.name)]
                sums[tgt_idx] += matrix[src_idx, tgt_idx]

    return sums


def is_consistent(
    matrix: np.ndarray,
    scenario: dict[str, str],
    drivers: Sequence[Driver],
    state_index: dict[tuple[str, str], int],
) -> bool:
    """A scenario is consistent if no driver would prefer to switch its state."""
    sums = compute_impact_sums(matrix, scenario, drivers, state_index)

    for driver in drivers:
        active_state = scenario[driver.name]
        active_sum = sums[state_index[(driver.name, active_state)]]
        for s in driver.states:
            if s.name == active_state:
                continue
            if sums[state_index[(driver.name, s.name)]] > active_sum:
                return False
    return True


def find_consistent_scenarios(
    matrix: np.ndarray,
    drivers: Sequence[Driver],
) -> list[dict[str, str]]:
    """Brute-force: enumerate all combinations, return consistent ones."""
    state_index = build_state_index(drivers)
    state_lists = [[s.name for s in d.states] for d in drivers]
    driver_names = [d.name for d in drivers]

    consistent = []
    for combo in itertools.product(*state_lists):
        scenario = dict(zip(driver_names, combo))
        if is_consistent(matrix, scenario, drivers, state_index):
            consistent.append(scenario)

    return consistent
