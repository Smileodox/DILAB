"""Scenario Generation pipeline step.

Input: data/outputs/merge_state.json + data/outputs/cib_state.json (or fixtures)
Output: data/outputs/scenario_state.json

Owner: Branch 3 (feature/scenario-generation)
"""


def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    cib_state_path: str = "data/outputs/cib_state.json",
    output_path: str = "data/outputs/scenario_state.json",
) -> dict:
    raise NotImplementedError("TODO: Branch 3 — extract from notebooks/06_scenario_generation.ipynb")
