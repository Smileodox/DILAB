"""Tests for src/pipeline/projection.py — PCA config projection + honest structure verdict.

Two regimes, mirroring the structure-test logic:
  - a clearly clustered config field → high PC1 share, named axes, usable clusters;
  - a uniform-random field → low PC1, no usable clusters (the honest default).
"""
from __future__ import annotations

import random

from src.pipeline import projection, structure


def _morphbox(n_drivers=4, n_manif=4):
    """Synthetic morphbox: ``n_drivers`` drivers, each with ``n_manif`` ordered states."""
    drivers = [f"d{j}" for j in range(n_drivers)]
    manifestations = {d: [f"{d}m{i}" for i in range(n_manif)] for d in drivers}
    all_manif = [
        {"id": f"{d}m{i}", "driver_id": d, "label": f"{d} state {i}", "description": ""}
        for d in drivers for i in range(n_manif)
    ]
    return {"drivers": drivers, "manifestations": manifestations, "all_manifestations": all_manif}


def _scenario(box, picks, sid):
    """One scenario picking manifestation index ``picks[j]`` for driver j."""
    assumptions = [
        {"driver_id": d, "manifestation_id": box["manifestations"][d][picks[j]]}
        for j, d in enumerate(box["drivers"])
    ]
    return {"id": sid, "type": "evolutionary", "assumptions": assumptions}


def _clustered_scenarios(box, copies=6):
    """Four well-separated archetypes (all-index-0 … all-index-3), each repeated."""
    nd, nm = len(box["drivers"]), len(box["manifestations"][box["drivers"][0]])
    out = []
    for c in range(min(4, nm)):
        for r in range(copies):
            out.append(_scenario(box, [c] * nd, f"c{c}_{r}"))
    return out


def test_clustered_field_has_named_axes_and_usable_clusters():
    box = _morphbox()
    scenarios = _clustered_scenarios(box)

    res = projection.project_config(scenarios, box, null_trials=8, seed=42)

    # coords: one [x, y] per scenario, finite
    assert set(res["coords"]) == {s["id"] for s in scenarios}
    for xy in res["coords"].values():
        assert len(xy) == 2 and all(isinstance(v, float) for v in xy)

    # axes carry a real dominant direction with driver loadings + a readable label
    assert res["axes"]["pc1"]["share"] > 0.3
    assert res["axes"]["pc1"]["drivers"], "PC1 should load on at least one driver"
    assert isinstance(res["axes"]["pc1"]["label"], str) and res["axes"]["pc1"]["label"]

    # four separated archetypes → usable clusters above the null
    assert res["structure"]["has_usable_clusters"] is True
    assert res["structure"]["above_null"] is True


def test_random_field_has_no_usable_clusters():
    box = _morphbox()
    rng = random.Random(0)
    scenarios = structure.random_field_scenarios(box["drivers"], box["manifestations"], n=24, rng=rng)

    res = projection.project_config(scenarios, box, null_trials=8, seed=0)

    # the honest verdict on a uniform field: no clusters to read as archetypes
    assert res["structure"]["has_usable_clusters"] is False
    # PC1 captures little — no dominant axis in a diffuse field
    assert res["structure"]["pc1_share"] < 0.6
    # parcoords spec is still well-formed
    assert len(res["parcoords"]["drivers"]) == len(box["drivers"])
    assert len(res["parcoords"]["rows"]) == len(scenarios)


def test_representatives_along_axis_span_the_continuum():
    # A continuum along PC1: reps should span end-to-end (include the extremes) and be distinct.
    coords = {f"s{i}": [float(i), 0.0] for i in range(20)}  # x = 0..19 along the axis
    reps = projection.representatives_along_axis(coords, k=5, axis=0)
    assert len(reps) == 5
    assert len(set(reps)) == 5                     # distinct
    xs = sorted(coords[r][0] for r in reps)
    assert xs[0] == 0.0 and xs[-1] == 19.0         # spans both poles
    assert xs == sorted(xs)                        # ordered along the axis


def test_representatives_along_axis_fewer_than_k():
    coords = {"a": [1.0, 0.0], "b": [2.0, 0.0]}
    reps = projection.representatives_along_axis(coords, k=5)
    assert set(reps) == {"a", "b"}


def test_parcoords_values_index_into_driver_manifestations():
    box = _morphbox()
    scenarios = _clustered_scenarios(box, copies=2)

    res = projection.project_config(scenarios, box, null_trials=4, seed=1)
    pc = res["parcoords"]

    assert len(pc["drivers"]) == len(box["drivers"])
    for drv in pc["drivers"]:
        assert len(drv["manifestations"]) == len(box["manifestations"][drv["driver_id"]])
    for row in pc["rows"]:
        assert len(row["values"]) == len(box["drivers"])
        for j, v in enumerate(row["values"]):
            # every clustered scenario assigns a real manifestation → valid index
            assert 0 <= v < len(pc["drivers"][j]["manifestations"])
