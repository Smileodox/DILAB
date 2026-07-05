"""Cross-function collinearity diagnostic for the functional/Zwicky morphological field.

The functional path's weak continuum (silhouette ~0.12) has a *nameable* cause: the extracted
FUNCTIONS are not independent morphological dimensions — several re-express the SAME latent axis
(e.g. raw-central ↔ reduced-edge), so the field is effectively one axis measured N times. A field
of N copies of one axis yields a smooth continuum, never clusters, by construction.

This module MEASURES that. It represents each function by the principal direction its competing
directions span in embedding space, then asks:
  - how many INDEPENDENT such axes the functions span — the participation ratio of the stacked
    per-function axis vectors (``latent_axes``); and
  - which functions collapse onto one axis — connected components of pairwise |cosine|.

It is the cause-side complement to the null-model structure test (``structure.py``): structure.py
says "the field is ≈ random"; this says "…because the drivers are collinear." Naming the artifact
is the legitimacy gate — we act on collinearity only if it is demonstrably present.

Pure / numpy-only given embeddings (unit-testable offline); ``analyze_collinearity`` is the thin
``embed()``-backed wrapper that runs it on a parsed morphbox.
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _principal_axis(vecs: np.ndarray) -> np.ndarray:
    """Unit vector of the dominant direction a function's manifestation embeddings span.

    ``vecs``: (k, d) embeddings of one function's k competing directions (k >= 2). Returns the
    top right-singular vector of the centred matrix — the axis those directions vary along. The
    sign is arbitrary (SVD ambiguity); downstream measures are sign-invariant.
    """
    if vecs.shape[0] < 2:
        return np.zeros(vecs.shape[1])
    xc = vecs - vecs.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    return _unit(vt[0])


def function_axes(function_ids, manifs_by_fid, emb_by_manif):
    """Stack each function's principal spread-axis into an (n_functions, d) unit-vector matrix.

    Functions with <2 embeddable directions are skipped (no axis definable). Returns
    ``(axes, kept_function_ids)``.
    """
    rows, kept = [], []
    for fid in function_ids:
        mids = [m for m in manifs_by_fid.get(fid, []) if m in emb_by_manif]
        if len(mids) < 2:
            continue
        vecs = np.asarray([emb_by_manif[m] for m in mids], dtype=float)
        axis = _principal_axis(vecs)
        if float(np.linalg.norm(axis)) == 0.0:
            continue
        rows.append(axis)
        kept.append(fid)
    return (np.asarray(rows, dtype=float) if rows else np.zeros((0, 0))), kept


def _participation_ratio(sv: np.ndarray) -> float:
    """Effective number of dimensions from a singular-value spectrum: (Σv)² / Σv², v = σ².

    Sign-invariant to per-row flips of the source matrix (depends only on σ²), so the arbitrary
    sign of each function's principal axis does not affect the latent-axis count.
    """
    var = sv ** 2
    total = float(var.sum())
    if total == 0.0:
        return float(len(sv))
    return float((var.sum() ** 2) / (var ** 2).sum())


def _components(sim: np.ndarray, threshold: float) -> list[list[int]]:
    """Connected components where ``sim[i,j] >= threshold`` (union-find)."""
    n = sim.shape[0]
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def collinearity_stats(axes: np.ndarray, function_ids, sim_threshold: float = 0.5) -> dict:
    """Latent-axis count + collinear groups from per-function axis vectors.

    ``axes``: (n, d) unit vectors, one per function. Returns ``latent_axes`` (participation ratio,
    sign-invariant), ``mean_abs_cos`` (mean off-diagonal |cosine|), and the function-id groups
    that collapse onto a shared axis (|cos| >= ``sim_threshold``).
    """
    n = int(axes.shape[0]) if axes.size else 0
    if n == 0:
        return {"n_functions": 0, "latent_axes": 0.0, "mean_abs_cos": 0.0,
                "groups": [], "n_axis_groups": 0, "largest_group": 0}
    sv = np.linalg.svd(axes, compute_uv=False)
    latent = _participation_ratio(sv)
    acos = np.abs(axes @ axes.T)
    off = acos[~np.eye(n, dtype=bool)]
    comp = _components(acos, sim_threshold)
    groups = [[function_ids[i] for i in c] for c in comp if len(c) >= 2]
    return {
        "n_functions": n,
        "latent_axes": round(latent, 3),
        "mean_abs_cos": round(float(off.mean()) if off.size else 0.0, 4),
        "groups": groups,
        "n_axis_groups": len(comp),
        "largest_group": max((len(c) for c in comp), default=0),
    }


def analyze_collinearity(morphbox: dict, name_by_fid: dict | None = None,
                         sim_threshold: float = 0.5) -> dict:
    """Embed a functional morphbox's directions and report cross-function collinearity.

    ``morphbox``: parsed ``morphbox_*_state.json`` (``drivers`` = function ids, ``manifestations``,
    ``all_manifestations``). Adds readable ``group_names`` when ``name_by_fid`` is supplied.
    """
    from src.llm import embed

    name_by_fid = name_by_fid or {}
    texts, ids = [], []
    for m in morphbox["all_manifestations"]:
        label, desc = m.get("label", ""), m.get("description", "")
        texts.append(f"{label}: {desc}" if desc else label)
        ids.append(m["id"])
    emb_by_manif = {mid: v for mid, v in zip(ids, embed(texts))}
    axes, kept = function_axes(morphbox["drivers"], morphbox["manifestations"], emb_by_manif)
    stats = collinearity_stats(axes, kept, sim_threshold=sim_threshold)
    stats["kept_functions"] = len(kept)
    stats["group_names"] = [[name_by_fid.get(fid, fid) for fid in g] for g in stats["groups"]]
    return stats
