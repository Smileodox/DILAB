"""Merge Drivers pipeline step.

Input: data/outputs/bom_state.json + data/outputs/trend_state.json
Output: data/outputs/merge_state.json

Owner: NB04 Merge-Step (after Branch 1+2 are merged)
"""


def run(
    bom_state_path: str = "data/outputs/bom_state.json",
    trend_state_path: str = "data/outputs/trend_state.json",
    output_path: str = "data/outputs/merge_state.json",
) -> dict:
    raise NotImplementedError("TODO: NB04 step — extract from notebooks/04_merge_drivers.ipynb")
