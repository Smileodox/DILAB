"""Scenario Landscape: embed narratives → UMAP 2D projection.

Input: data/outputs/scenario_state.json
Output: data/outputs/landscape_state.json
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from umap import UMAP

from src.llm import embed

log = logging.getLogger(__name__)

DATA_DIR = "data/outputs"


def run(
    scenario_state_path: str = os.path.join(DATA_DIR, "scenario_state.json"),
    output_path: str = os.path.join(DATA_DIR, "landscape_state.json"),
) -> dict:
    with open(scenario_state_path) as f:
        scenarios = json.load(f)["scenarios"]

    n = len(scenarios)
    if n < 4:
        log.warning("Too few scenarios (%d) for meaningful UMAP projection", n)
        return {"points": [], "similarity_matrix": [], "metadata": {}}

    narratives = [s["narrative"][:8000] for s in scenarios]
    log.info("Embedding %d scenario narratives", n)
    embeddings = np.array(embed(narratives))

    n_neighbors = min(15, n - 1)
    log.info("Running UMAP (n_neighbors=%d)", n_neighbors)
    reducer = UMAP(
        n_components=2,
        n_neighbors=n_neighbors,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(embeddings)

    sim_matrix = cosine_similarity(embeddings)

    total_space = 1
    for s in scenarios:
        if s.get("assumptions"):
            total_space = 4 ** len(s["assumptions"])
            break

    points = []
    for i, s in enumerate(scenarios):
        points.append({
            "scenario_id": s["id"],
            "title": s["title"],
            "type": s.get("type", "evolutionary"),
            "is_fixed_point": s.get("is_fixed_point", True),
            "consistency_score": 0.0,
            "coverage_ratio": s.get("coverage_ratio", 1.0),
            "seed_id": s.get("seed_id", ""),
            "x": round(float(coords[i, 0]), 4),
            "y": round(float(coords[i, 1]), 4),
        })

    # Enrich with consistency scores from consistency_state if available
    consistency_path = os.path.join(DATA_DIR, "consistency_state.json")
    if os.path.exists(consistency_path):
        with open(consistency_path) as f:
            configs = json.load(f).get("configs", [])
        score_by_id = {c.get("id", ""): c.get("consistency_score", 0) for c in configs}
        for p in points:
            if p["seed_id"] in score_by_id:
                p["consistency_score"] = score_by_id[p["seed_id"]]

    state = {
        "points": points,
        "similarity_matrix": [[round(float(v), 4) for v in row] for row in sim_matrix],
        "scenario_ids": [p["scenario_id"] for p in points],
        "metadata": {
            "n_scenarios": n,
            "n_fixed_points": sum(1 for p in points if p["is_fixed_point"]),
            "n_near_neighbors": sum(1 for p in points if not p["is_fixed_point"]),
            "total_combinatorial_space": total_space,
            "embedding_model": "text-embedding-3-small",
            "embedding_dim": embeddings.shape[1],
            "umap_params": {
                "n_neighbors": n_neighbors,
                "min_dist": 0.1,
                "metric": "cosine",
            },
        },
    }

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    log.info("Landscape saved: %d points, %d dims → 2D", n, embeddings.shape[1])
    return state
