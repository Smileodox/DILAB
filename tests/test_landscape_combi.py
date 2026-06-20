"""Offline test for the combinatorial-path landscape change.

Passing precomputed embeddings lets landscape.run() skip the Azure embed call, so the
UMAP projection + point schema can be verified without network access.
"""
import json

import numpy as np

from src.pipeline import landscape


def _scenarios(n: int):
    return [
        {
            "id": f"s{i}",
            "title": f"Scenario {i}",
            "narrative": "placeholder narrative",
            "type": "evolutionary",
            "is_fixed_point": False,
            "coverage_ratio": 1.0,
            "seed_id": "",
        }
        for i in range(n)
    ]


def test_landscape_uses_precomputed_embeddings(tmp_path):
    n = 8
    scen_path = tmp_path / "scenario_state_combi.json"
    scen_path.write_text(json.dumps({"scenarios": _scenarios(n)}))
    out_path = tmp_path / "landscape_state_combi.json"
    embeddings = np.random.RandomState(0).rand(n, 16)

    # Non-existent consistency path → enrichment is simply skipped (no error).
    state = landscape.run(
        str(scen_path),
        str(out_path),
        str(tmp_path / "missing.json"),
        embeddings=embeddings,
    )

    assert len(state["points"]) == n
    assert all("x" in p and "y" in p for p in state["points"])
    assert all(isinstance(p["consistency_score"], (int, float)) for p in state["points"])
    assert out_path.exists()
    assert state["metadata"]["embedding_dim"] == 16
