"""Scenario Evaluation pipeline step.

Input: data/outputs/scenario_state.json + merge_state.json + kb_state.json (or fixtures)
Output: data/outputs/final_analysis.json

Owner: Branch 4 (feature/scenario-evaluation)
"""


def run(
    scenario_state_path: str = "data/outputs/scenario_state.json",
    merge_state_path: str = "data/outputs/merge_state.json",
    kb_state_path: str = "data/outputs/kb_state.json",
    output_path: str = "data/outputs/final_analysis.json",
) -> dict:
    raise NotImplementedError("TODO: Branch 4 — extract from notebooks/07_analysis.ipynb")
