from collections import Counter

import numpy as np

from src.pipeline.clustering import cluster_and_select


def _three_clusters():
    """Nine points in three near-orthogonal directions (cosine-separable)."""
    pts = [
        [1, 0, 0, 0], [0.99, 0.02, 0, 0], [0.98, 0, 0.02, 0],
        [0, 1, 0, 0], [0.02, 0.99, 0, 0], [0, 0.98, 0.02, 0],
        [0, 0, 1, 0], [0, 0.02, 0.99, 0], [0, 0, 0.98, 0.02],
    ]
    ids = [f"s{i}" for i in range(9)]
    return np.array(pts, dtype=float), ids


class TestClusterAndSelect:
    def test_fixed_k(self):
        emb, ids = _three_clusters()
        out = cluster_and_select(emb, ids, k=3)
        assert out["k"] == 3
        assert len(out["representative_ids"]) == 3
        assert len(set(out["labels"])) == 3
        assert all(r in ids for r in out["representative_ids"])

    def test_auto_k_recovers_three(self):
        emb, ids = _three_clusters()
        out = cluster_and_select(emb, ids, k=None, k_range=(2, 5))
        assert out["k"] == 3
        assert out["silhouette"] > 0.5

    def test_each_cluster_equal_size(self):
        emb, ids = _three_clusters()
        out = cluster_and_select(emb, ids, k=3)
        assert sorted(Counter(out["labels"]).values()) == [3, 3, 3]

    def test_representatives_are_distinct(self):
        emb, ids = _three_clusters()
        out = cluster_and_select(emb, ids, k=3)
        assert len(set(out["representative_ids"])) == 3

    def test_too_few_points_single_cluster(self):
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])
        out = cluster_and_select(emb, ["a", "b"])
        assert out["k"] == 1
        assert len(out["representative_ids"]) == 1

    def test_empty(self):
        out = cluster_and_select(np.zeros((0, 3)), [])
        assert out["k"] == 0
        assert out["labels"] == []
