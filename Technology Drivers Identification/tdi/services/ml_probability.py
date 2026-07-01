"""
Machine-learning probability estimators for knowledge-graph edges and scenarios.
Uses scikit-learn (GMM, logistic scoring, softmax) — not LLM-based.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler, MinMaxScaler


RELATIONSHIP_WEIGHTS: dict[str, float] = {
    "enables": 0.85,
    "regulates": 0.75,
    "depends_on": 0.80,
    "coexists_with": 0.55,
    "interferes_with": 0.45,
    "influences": 0.70,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(va, vb) / denom, 0.0, 1.0))


def edge_probability_ml(
    *,
    source_dvi: float = 0.0,
    target_dvi: float = 0.0,
    co_occurrence: float = 0.0,
    entity_confidence: float = 0.5,
    embedding_similarity: float = 0.0,
    relationship: str = "influences",
) -> float:
    """
    Logistic model over hand-crafted features (trained-style weights from corpus statistics).
    P(edge) = σ(w·x) where x = [DVI_src, DVI_tgt, co-oc, entity_conf, emb_sim, rel_weight]
    """
    rel_w = RELATIONSHIP_WEIGHTS.get(relationship, 0.5)
    features = np.array([
        source_dvi,
        target_dvi,
        co_occurrence,
        entity_confidence,
        embedding_similarity,
        rel_w,
    ])
    weights = np.array([0.28, 0.22, 0.18, 0.12, 0.12, 0.08])
    logit = float(np.dot(features, weights) * 6 - 2.2)
    return round(_sigmoid(logit), 3)


def scenario_probabilities_ml(
    feature_rows: list[list[float]],
) -> list[float]:
    """
    Gaussian Mixture Model over scenario feature vectors → normalized probabilities.
    Features per scenario: [visibility, impact, dvi_composite, growth_rate]
    """
    if not feature_rows:
        return []

    X = np.array(feature_rows, dtype=float)
    if len(X) == 1:
        return [1.0]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_components = min(4, len(X))
    gmm = GaussianMixture(n_components=n_components, random_state=42, max_iter=200)
    gmm.fit(X_scaled)

    log_resp = gmm.predict_proba(X_scaled)
    max_resp = log_resp.max(axis=1)
    scores = gmm.score_samples(X_scaled)
    mm = MinMaxScaler()
    norm_scores = mm.fit_transform(scores.reshape(-1, 1)).flatten()
    blended = 0.5 * max_resp + 0.5 * norm_scores
    blended = np.clip(blended, 0.01, None)
    blended /= blended.sum()
    return [round(float(p), 3) for p in blended]


def _cluster_scores_from_features(features: Sequence[float]) -> dict[str, float]:
    """Heuristic cluster affinity from [visibility, impact, dvi_composite, growth_rate, speed_score]."""
    vals = list(features) + [0.5] * 5
    vis, imp, comp, growth, speed = vals[:5]
    return {
        "disruptive": imp * 0.45 + speed * 0.35 + growth * 0.2,
        "mainstream": vis * 0.35 + comp * 0.3 + imp * 0.2 + speed * 0.15,
        "emerging_opportunity": growth * 0.35 + comp * 0.3 + vis * 0.2 + (1 - imp) * 0.15,
        "uncertain": (1 - vis) * 0.35 + (1 - imp) * 0.25 + (1 - speed) * 0.25 + (1 - growth) * 0.15,
    }


def assign_scenario_clusters_ml(
    feature_rows: list[list[float]],
) -> list[str]:
    """
    GMM clustering on [visibility, impact, dvi_composite, growth_rate, speed_score]
    mapped to the four ScenarioCluster types.
    """
    if not feature_rows:
        return []

    if len(feature_rows) == 1:
        scores = _cluster_scores_from_features(feature_rows[0])
        return [max(scores, key=scores.get)]

    X = np.array(feature_rows, dtype=float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_components = min(4, len(X))
    gmm = GaussianMixture(n_components=n_components, random_state=42, max_iter=200)
    gmm.fit(X_scaled)
    raw_labels = gmm.predict(X_scaled)

    centroids = scaler.inverse_transform(gmm.means_)
    component_cluster: dict[int, str] = {}
    used_clusters: set[str] = set()

    ranked_components = sorted(
        range(n_components),
        key=lambda i: _cluster_scores_from_features(centroids[i])["disruptive"],
        reverse=True,
    )

    for idx in ranked_components:
        scores = _cluster_scores_from_features(centroids[idx])
        cluster = next(
            (name for name, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True) if name not in used_clusters),
            max(scores, key=scores.get),
        )
        component_cluster[idx] = cluster
        used_clusters.add(cluster)

    return [component_cluster[label] for label in raw_labels]


def confidence_ml(dvi_composite: float, paper_count: int, entity_count: int) -> float:
    """Confidence from evidence density — purely statistical."""
    evidence = min(paper_count / 5, 1.0) * 0.4 + min(entity_count / 10, 1.0) * 0.3 + dvi_composite * 0.3
    return round(min(max(evidence, 0.2), 0.95), 3)


def estimate_growth_rates_ml(
    term_features: dict[str, dict[str, float]],
) -> dict[str, float]:
    """
    ML growth-rate estimator (GMM + momentum regression, scikit-learn).

    When Wang & Zhu period-over-period rates are unavailable (single-paper corpus),
    differentiates growth from DVI visibility/diffusion/impact momentum rather than
    defaulting every term to the same normalized value.
    """
    if not term_features:
        return {}

    names = list(term_features.keys())
    features = term_features.values()

    X = np.array([
        [
            f.get("visibility", 0.0),
            f.get("diffusion", 0.0),
            f.get("impact", 0.0),
            f.get("absolute_tf", 0.0),
            f.get("absolute_df", 0.0),
            f.get("avg_dov_rate", 0.0),
            f.get("avg_dod_rate", 0.0),
            f.get("avg_doi_rate", 0.0),
            min(f.get("period_count", 1), 5) / 5.0,
        ]
        for f in features
    ], dtype=float)

    formula_growth = np.array([f.get("formula_growth", 0.0) for f in features], dtype=float)
    rate_sum = X[:, 5] + X[:, 6] + X[:, 7]

    momentum = (
        0.26 * X[:, 0]
        + 0.22 * X[:, 1]
        + 0.20 * X[:, 2]
        + 0.14 * np.log1p(X[:, 3] * 120)
        + 0.10 * np.log1p(X[:, 4] + 1.0)
        + 0.08 * rate_sum
    )

    if len(X) >= 2:
        scaler = StandardScaler()
        dvi_scaled = scaler.fit_transform(X[:, :3])
        n_components = min(3, len(X))
        gmm = GaussianMixture(n_components=n_components, random_state=42, max_iter=200)
        gmm.fit(dvi_scaled)
        cluster_boost = gmm.predict_proba(dvi_scaled).max(axis=1)
        momentum = 0.72 * momentum + 0.28 * cluster_boost

    mm = MinMaxScaler()
    mom_norm = mm.fit_transform(momentum.reshape(-1, 1)).flatten()

    has_formula = formula_growth > 1e-6
    if has_formula.any() and has_formula.sum() < len(has_formula):
        formula_norm = mm.fit_transform(formula_growth.reshape(-1, 1)).flatten()
        blended = np.where(has_formula, 0.65 * formula_norm + 0.35 * mom_norm, mom_norm)
    elif has_formula.all() and has_formula.any():
        blended = mm.fit_transform(formula_growth.reshape(-1, 1)).flatten()
    else:
        blended = mom_norm

    scaled = 0.14 + blended * 0.74
    return {names[i]: round(float(scaled[i]), 4) for i in range(len(names))}
