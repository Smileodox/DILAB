"""Embedding-space clustering of scenario narratives → one representative per cluster.

The combinatorial method generates many short narratives; this groups them by semantic
similarity (KMeans on L2-normalised narrative embeddings, so Euclidean ≈ cosine) and
picks the most-typical narrative of each cluster as the headline "representative"
scenario. The number of clusters is chosen automatically by silhouette score, or fixed.

Pure / numpy-only: takes embeddings in, returns labels + representative ids. No LLM call
here (the caller embeds the narratives), which keeps it unit-testable offline.
"""

from __future__ import annotations

import logging

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

log = logging.getLogger(__name__)


def config_matrix(scenarios, manifestation_ids) -> np.ndarray:
    """One-hot encode each scenario's manifestation assignments (rows align to scenarios).

    Each scenario becomes a binary vector over the full manifestation vocabulary: 1 where
    that manifestation is part of the scenario's configuration. This represents a scenario
    by WHAT it is (its driver-state recipe), not by its narrative prose — so distances
    reflect structural difference, which narrative embeddings of same-domain text cannot.
    """
    idx = {m: i for i, m in enumerate(manifestation_ids)}
    x = np.zeros((len(scenarios), len(manifestation_ids)), dtype=float)
    for r, s in enumerate(scenarios):
        for a in s.get("assumptions", []):
            j = idx.get(a.get("manifestation_id"))
            if j is not None:
                x[r, j] = 1.0
    return x


def _normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


def _representative(x_norm: np.ndarray, idxs: list[int], ids: list[str]) -> str:
    """Id of the point closest to the (normalised) mean of its cluster."""
    centroid = x_norm[idxs].mean(axis=0)
    cnorm = np.linalg.norm(centroid)
    if cnorm > 0:
        centroid = centroid / cnorm
    sims = x_norm[idxs] @ centroid
    return ids[idxs[int(np.argmax(sims))]]


def cluster_and_select(
    embeddings,
    ids: list[str],
    k: int | None = None,
    k_range: tuple[int, int] = (4, 10),
    seed: int = 42,
) -> dict:
    """Cluster narrative embeddings and pick one representative per cluster.

    Args:
        embeddings: (n, d) array-like of narrative embeddings, aligned to ``ids``.
        ids: scenario ids, one per embedding row.
        k: fixed number of clusters; if falsy, auto-select by silhouette over ``k_range``.
        k_range: (min, max) inclusive bounds for the silhouette sweep.
        seed: KMeans random_state for reproducibility.

    Returns:
        {"labels": [int per point], "representative_ids": [str per cluster],
         "k": int, "silhouette": float}
    """
    x = _normalize(np.asarray(embeddings, dtype=float))
    n = len(ids)

    if n == 0:
        return {"labels": [], "representative_ids": [], "k": 0, "silhouette": 0.0}
    if n <= 2:
        # Too few points to cluster meaningfully — treat as a single group.
        return {
            "labels": [0] * n,
            "representative_ids": [_representative(x, list(range(n)), ids)],
            "k": 1,
            "silhouette": 0.0,
        }

    if k and k > 0:
        candidate_ks = [min(k, n - 1)]
    else:
        k_min = max(2, k_range[0])
        k_max = min(k_range[1], n - 1)
        candidate_ks = list(range(k_min, max(k_min, k_max) + 1))

    best: tuple[float, int, np.ndarray] | None = None  # (silhouette, k, labels)
    for kk in candidate_ks:
        if kk < 2 or kk > n - 1:
            continue
        labels = KMeans(n_clusters=kk, random_state=seed, n_init=10).fit_predict(x)
        if len(set(labels.tolist())) < 2:
            continue
        sil = float(silhouette_score(x, labels, metric="cosine"))
        if best is None or sil > best[0]:
            best = (sil, kk, labels)

    if best is None:
        # Degenerate (e.g. all-identical embeddings): one cluster.
        return {
            "labels": [0] * n,
            "representative_ids": [_representative(x, list(range(n)), ids)],
            "k": 1,
            "silhouette": 0.0,
        }

    sil, chosen_k, labels_arr = best
    labels = labels_arr.tolist()
    representative_ids = [
        _representative(x, [i for i, lab in enumerate(labels) if lab == c], ids)
        for c in range(chosen_k)
        if any(lab == c for lab in labels)
    ]

    log.info("Clustering: k=%d, silhouette=%.3f, %d representatives", chosen_k, sil, len(representative_ids))
    return {
        "labels": labels,
        "representative_ids": representative_ids,
        "k": chosen_k,
        "silhouette": round(sil, 4),
    }
