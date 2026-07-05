"""Offline tests for the cross-function collinearity diagnostic (no LLM, synthetic embeddings).

Known-answer checks: N functions that all vary on ONE shared axis must read as ~1 latent axis
(one big group); N functions varying on distinct orthogonal axes must read as ~N latent axes
(no group). This is what makes the diagnostic trustworthy as the cause-side referee.
"""
import numpy as np

from src.pipeline.collinearity import (
    _participation_ratio,
    _principal_axis,
    collinearity_stats,
    function_axes,
)


def _morphbox_like(n_functions, axis_of_function, d=6, noise=0.0, rng=None):
    """Build (manifs_by_fid, emb_by_manif) where each function's 2 directions sit at ±axis."""
    rng = rng or np.random.RandomState(0)
    manifs, emb = {}, {}
    for fi in range(n_functions):
        axis = axis_of_function(fi)
        fid = f"f{fi}"
        a, b = f"{fid}_a", f"{fid}_b"
        manifs[fid] = [a, b]
        na = noise * rng.randn(d) if noise else 0.0
        nb = noise * rng.randn(d) if noise else 0.0
        emb[a] = (+axis + na).tolist()
        emb[b] = (-axis + nb).tolist()
    return manifs, emb


def test_principal_axis_two_points():
    vecs = np.array([[1.0, 0, 0], [-1.0, 0, 0]])
    ax = _principal_axis(vecs)
    assert abs(abs(ax[0]) - 1.0) < 1e-9
    assert abs(ax[1]) < 1e-9 and abs(ax[2]) < 1e-9


def test_participation_ratio_bounds():
    # one dominant singular value → ~1 effective dim
    assert abs(_participation_ratio(np.array([5.0, 0.0, 0.0])) - 1.0) < 1e-9
    # five equal → 5 effective dims
    assert abs(_participation_ratio(np.array([1.0] * 5)) - 5.0) < 1e-9


def test_collinear_functions_collapse_to_one_axis():
    d = 6
    e0 = np.eye(d)[0]
    manifs, emb = _morphbox_like(5, lambda fi: e0, d=d, noise=0.02)
    axes, kept = function_axes([f"f{i}" for i in range(5)], manifs, emb)
    stats = collinearity_stats(axes, kept, sim_threshold=0.5)
    assert stats["n_functions"] == 5
    assert stats["latent_axes"] < 1.5          # ~1 real axis
    assert stats["mean_abs_cos"] > 0.9         # all axes nearly parallel
    assert stats["largest_group"] == 5         # one big collinear group
    assert len(stats["groups"]) == 1


def test_independent_functions_span_many_axes():
    d = 6
    E = np.eye(d)
    manifs, emb = _morphbox_like(5, lambda fi: E[fi], d=d, noise=0.0)
    axes, kept = function_axes([f"f{i}" for i in range(5)], manifs, emb)
    stats = collinearity_stats(axes, kept, sim_threshold=0.5)
    assert stats["latent_axes"] > 4.5          # ~5 independent axes
    assert stats["mean_abs_cos"] < 0.1         # orthogonal
    assert stats["groups"] == []               # nothing collapses
    assert stats["largest_group"] == 1


def test_functions_with_too_few_directions_are_skipped():
    manifs = {"f0": ["a", "b"], "f1": ["c"]}  # f1 has one direction → skipped
    emb = {"a": [1.0, 0, 0], "b": [-1.0, 0, 0], "c": [0, 1.0, 0]}
    axes, kept = function_axes(["f0", "f1"], manifs, emb)
    assert kept == ["f0"]
    assert axes.shape[0] == 1


def test_empty_is_safe():
    stats = collinearity_stats(np.zeros((0, 0)), [])
    assert stats["n_functions"] == 0 and stats["latent_axes"] == 0.0
