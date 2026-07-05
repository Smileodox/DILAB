import random

import numpy as np

from src.pipeline.structure import (
    analyze,
    null_distribution,
    random_field_scenarios,
    structure_stats,
)


def _field(n_drivers=9, n_states=4):
    """A morphbox dict with ``n_drivers`` functions, each with ``n_states`` manifestations."""
    drivers, manifestations, all_manifs = [], {}, []
    for d in range(n_drivers):
        did = f"d{d}"
        mids = [f"d{d}_m{s}" for s in range(n_states)]
        drivers.append(did)
        manifestations[did] = mids
        all_manifs.extend({"id": m, "driver_id": did} for m in mids)
    return {"drivers": drivers, "manifestations": manifestations, "all_manifestations": all_manifs}


class TestStructureStats:
    def test_clustered_field_has_low_effective_dim(self):
        # Three repeated configurations → variance concentrates, clusters separate.
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        archetypes = [
            [mb["manifestations"][d][0] for d in mb["drivers"]],
            [mb["manifestations"][d][1] for d in mb["drivers"]],
            [mb["manifestations"][d][2] for d in mb["drivers"]],
        ]
        scens = [{"id": f"s{i}", "assumptions": [{"manifestation_id": m} for m in archetypes[i % 3]]}
                 for i in range(60)]
        from src.pipeline.clustering import config_matrix
        stats = structure_stats(config_matrix(scens, vocab), [s["id"] for s in scens])
        assert stats["best_silhouette"] > 0.9      # three tight, well-separated blobs
        assert stats["effective_dim"] < 3.5        # variance lives on ~2 axes

    def test_uniform_field_is_high_dim_and_unclustered(self):
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        rng = random.Random(0)
        scens = random_field_scenarios(mb["drivers"], mb["manifestations"], 120, rng)
        from src.pipeline.clustering import config_matrix
        stats = structure_stats(config_matrix(scens, vocab), [f"r{i}" for i in range(120)])
        assert stats["best_silhouette"] < 0.2      # no real clusters in a uniform cloud
        assert stats["effective_dim"] > 10         # isotropic: many comparable axes


class TestNullComparison:
    def test_uniform_sample_is_indistinguishable_from_null(self):
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        rng = random.Random(7)
        scens = random_field_scenarios(mb["drivers"], mb["manifestations"], 120, rng)
        scens = [{"id": f"s{i}", **s} for i, s in enumerate(scens)]
        res = analyze(scens, mb, null_trials=15, seed=1)
        assert res["usable_structure"] is False
        assert res["verdict"] == "≈ uniform random"
        assert abs(res["z_scores"]["best_silhouette"]) < 3.0

    def test_clustered_sample_is_distinguishable_from_null(self):
        mb = _field()
        archetypes = [
            [mb["manifestations"][d][0] for d in mb["drivers"]],
            [mb["manifestations"][d][1] for d in mb["drivers"]],
        ]
        scens = [{"id": f"s{i}", "assumptions": [{"manifestation_id": m} for m in archetypes[i % 2]]}
                 for i in range(60)]
        res = analyze(scens, mb, null_trials=15, seed=1)
        assert res["usable_structure"] is True
        assert res["verdict"] == "usable structure"

    def test_null_distribution_shape(self):
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        agg = null_distribution(mb["drivers"], mb["manifestations"], vocab, n=80, trials=10)
        assert agg["trials"] == 10
        for key in ("effective_dim", "pc1", "best_silhouette"):
            assert agg[key]["std"] >= 0.0
            assert np.isfinite(agg[key]["mean"])


def _clustered_scens(mb, n_cols=2, copies=8):
    """Well-separated archetypes (all-index-c) → a well-defined dominant axis direction."""
    out = []
    for c in range(n_cols):
        for _ in range(copies):
            out.append({"assumptions": [{"manifestation_id": mb["manifestations"][d][c]}
                                        for d in mb["drivers"]]})
    return out


class TestAxisDirectionStability:
    def test_pc_loadings_are_unit_rows(self):
        from src.pipeline.structure import pc_loadings
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        L = pc_loadings(_clustered_scens(mb), vocab, k=3)
        assert L.shape[1] == len(vocab)
        for row in L:
            assert abs(float((row * row).sum()) - 1.0) < 1e-6

    def test_identical_field_is_maximally_stable(self):
        from src.pipeline.structure import axis_direction_stability
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        f = _clustered_scens(mb)
        r = axis_direction_stability(f, f, vocab, k=3)
        assert all(c > 0.99 for c in r["abs_cos"])   # a field's axes match themselves exactly
        assert r["stable_axes"] == len(r["abs_cos"])

    def test_random_fields_are_direction_unstable(self):
        import random
        from src.pipeline.structure import axis_direction_stability, random_field_scenarios
        mb = _field()
        vocab = [m["id"] for m in mb["all_manifestations"]]
        a = random_field_scenarios(mb["drivers"], mb["manifestations"], 80, random.Random(1))
        b = random_field_scenarios(mb["drivers"], mb["manifestations"], 80, random.Random(2))
        r = axis_direction_stability(a, b, vocab, k=3)
        # near-isotropic random fields share no stable axis direction (the honest signature)
        assert r["stable_axes"] <= 1
