import json
import random

import pytest

from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)
from src.pipeline import combinatorial
from src.pipeline.combinatorial import contradiction_ratio, sample_combinations


@pytest.fixture
def morph_box(morphbox_state):
    return MorphologicalBox(
        drivers=morphbox_state["drivers"],
        manifestations=morphbox_state["manifestations"],
        all_manifestations=[
            DriverManifestation(**m) for m in morphbox_state["all_manifestations"]
        ],
    )


@pytest.fixture
def cib_matrix(morphbox_state):
    return morphbox_state["cib_matrix"]


@pytest.fixture
def driver_index(morphbox_state):
    return morphbox_state["cib_driver_index"]


class TestContradictionRatio:
    def test_in_unit_interval(self, morph_box, cib_matrix, driver_index):
        rng = random.Random(0)
        for _ in range(20):
            cfg = {d: rng.choice(morph_box.manifestations[d]) for d in morph_box.drivers}
            cr = contradiction_ratio(cfg, morph_box, cib_matrix, driver_index)
            assert 0.0 <= cr <= 1.0

    def test_aligned_lower_than_misaligned(self, morph_box, cib_matrix, driver_index):
        # CIB row drv_rf→drv_ai is +2 (strong promote): an optimistic RF wants an
        # optimistic AI. Flipping AI to pessimistic must raise the contradiction ratio.
        opt = lambda d: morph_box.manifestations[d][0]
        mid = lambda d: morph_box.manifestations[d][1]
        pes = lambda d: morph_box.manifestations[d][-1]
        aligned = {"drv_rf": opt("drv_rf"), "drv_ai": opt("drv_ai"), "drv_quantum": mid("drv_quantum")}
        misaligned = {"drv_rf": opt("drv_rf"), "drv_ai": pes("drv_ai"), "drv_quantum": mid("drv_quantum")}
        cr_a = contradiction_ratio(aligned, morph_box, cib_matrix, driver_index)
        cr_b = contradiction_ratio(misaligned, morph_box, cib_matrix, driver_index)
        assert cr_a < cr_b

    def test_no_cib_edges_is_zero(self, morph_box, driver_index):
        # An all-zero CIB matrix means no constraints → no contradictions.
        zero = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        cfg = {d: morph_box.manifestations[d][0] for d in morph_box.drivers}
        assert contradiction_ratio(cfg, morph_box, zero, driver_index) == 0.0


class TestSampleCombinations:
    def test_deterministic_with_seed(self, morph_box, cib_matrix, driver_index):
        a = sample_combinations(morph_box, cib_matrix, driver_index, n_samples=10, reject_threshold=1.0, seed=7)
        b = sample_combinations(morph_box, cib_matrix, driver_index, n_samples=10, reject_threshold=1.0, seed=7)
        assert [c.configuration for c in a] == [c.configuration for c in b]

    def test_caps_at_n_samples(self, morph_box, cib_matrix, driver_index):
        res = sample_combinations(morph_box, cib_matrix, driver_index, n_samples=5, reject_threshold=1.0, seed=1)
        assert len(res) <= 5

    def test_covers_all_drivers(self, morph_box, cib_matrix, driver_index):
        res = sample_combinations(morph_box, cib_matrix, driver_index, n_samples=8, reject_threshold=1.0, seed=1)
        assert res
        for c in res:
            assert set(c.configuration.keys()) == set(morph_box.drivers)

    def test_reject_threshold_respected(self, morph_box, cib_matrix, driver_index):
        res = sample_combinations(
            morph_box, cib_matrix, driver_index,
            n_samples=27, oversample_factor=10.0, reject_threshold=0.3, seed=1,
        )
        assert all(c.contradiction_ratio <= 0.3 + 1e-9 for c in res)

    def test_looser_threshold_keeps_more(self, morph_box, cib_matrix, driver_index):
        strict = sample_combinations(
            morph_box, cib_matrix, driver_index,
            n_samples=27, oversample_factor=10.0, reject_threshold=0.2, seed=1,
        )
        loose = sample_combinations(
            morph_box, cib_matrix, driver_index,
            n_samples=27, oversample_factor=10.0, reject_threshold=0.9, seed=1,
        )
        assert len(loose) >= len(strict)

    def test_no_fixed_points_no_archetype_forcing(self, morph_box, cib_matrix, driver_index):
        res = sample_combinations(morph_box, cib_matrix, driver_index, n_samples=6, reject_threshold=1.0, seed=1)
        assert res
        assert all(not c.is_fixed_point for c in res)
        assert all(c.is_consistent and c.frequency == 1 for c in res)
        # scenario_type is inferred descriptively (one of the four labels), not forced.
        assert all(c.scenario_type in {"evolutionary", "disruptive", "cautionary", "wildcard"} for c in res)


class TestRun:
    def test_writes_valid_state(self, morphbox_state, tmp_path):
        # Build a cib_state matching the morphbox fixture (run() reads matrix + driver_ids).
        idx = morphbox_state["cib_driver_index"]
        driver_ids = sorted(idx, key=lambda d: idx[d])
        cib_state = {"matrix": morphbox_state["cib_matrix"], "driver_ids": driver_ids}

        morph_path = tmp_path / "morphbox.json"
        cib_path = tmp_path / "cib.json"
        out_path = tmp_path / "combinatorial_state.json"
        morph_path.write_text(json.dumps(morphbox_state))
        cib_path.write_text(json.dumps(cib_state))

        state = combinatorial.run(
            str(morph_path), str(cib_path), str(out_path),
            n_samples=10, reject_threshold=1.0, seed=1,
        )
        assert state["method"] == "combinatorial"
        assert state["n_combinations"] == len(state["configs"]) <= 10
        assert out_path.exists()

        # The state file must validate as ConsistencyResult so scenario_gen consumes it.
        configs = [ConsistencyResult(**c) for c in state["configs"]]
        assert all(not c.is_fixed_point for c in configs)
        assert all(set(c.configuration.keys()) == set(morphbox_state["drivers"]) for c in configs)
