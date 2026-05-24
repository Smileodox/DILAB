import pytest
from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)
from src.pipeline.morphological import (
    find_consistent_configs,
    infer_scenario_type,
    is_fixed_point,
    iterate_to_fixed_point,
    select_scenario_seeds,
    support_score,
)


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


class TestDriverManifestation:
    def test_fields(self):
        m = DriverManifestation(
            driver_id="drv_1",
            label="Test label",
            description="Test description",
            plausibility="high",
        )
        assert len(m.id) == 12
        assert m.driver_id == "drv_1"
        assert m.source_chunk_ids == []

    def test_from_fixture(self, morphbox_state):
        manifs = [
            DriverManifestation(**m) for m in morphbox_state["all_manifestations"]
        ]
        assert len(manifs) == 9
        assert all(m.plausibility in ("high", "medium", "low") for m in manifs)


class TestMorphologicalBox:
    def test_every_driver_has_manifestations(self, morph_box):
        for d in morph_box.drivers:
            assert d in morph_box.manifestations
            assert len(morph_box.manifestations[d]) >= 2

    def test_manifestation_count(self, morph_box):
        for d in morph_box.drivers:
            n = len(morph_box.manifestations[d])
            assert 2 <= n <= 4


class TestConsistencyResult:
    def test_from_fixture(self, consistency_state):
        configs = [ConsistencyResult(**c) for c in consistency_state["configs"]]
        assert len(configs) == 3
        assert all(c.is_consistent for c in configs)
        assert all(c.consistency_score > 0 for c in configs)


class TestSupportScore:
    def test_returns_float(self, morph_box, cib_matrix, driver_index):
        config = {d: morph_box.manifestations[d][0] for d in morph_box.drivers}
        score = support_score(
            "drv_rf", config["drv_rf"], config, morph_box, cib_matrix, driver_index
        )
        assert isinstance(score, float)

    def test_optimistic_drivers_push_via_positive_cib(
        self, morph_box, cib_matrix, driver_index
    ):
        config = {d: morph_box.manifestations[d][0] for d in morph_box.drivers}
        score_opt = support_score(
            "drv_ai", morph_box.manifestations["drv_ai"][0],
            config, morph_box, cib_matrix, driver_index,
        )
        score_pes = support_score(
            "drv_ai", morph_box.manifestations["drv_ai"][-1],
            config, morph_box, cib_matrix, driver_index,
        )
        # RF→AI is +2, RF is optimistic → should push AI toward optimistic
        assert score_opt > score_pes


class TestFixedPoint:
    def test_converges(self, morph_box, cib_matrix, driver_index):
        config = {d: morph_box.manifestations[d][1] for d in morph_box.drivers}
        result = iterate_to_fixed_point(
            config, morph_box, cib_matrix, driver_index
        )
        assert is_fixed_point(result, morph_box, cib_matrix, driver_index)

    def test_fixed_point_is_stable(self, morph_box, cib_matrix, driver_index):
        config = {d: morph_box.manifestations[d][0] for d in morph_box.drivers}
        result = iterate_to_fixed_point(
            config, morph_box, cib_matrix, driver_index
        )
        result2 = iterate_to_fixed_point(
            result, morph_box, cib_matrix, driver_index
        )
        assert result == result2


class TestFindConsistentConfigs:
    def test_finds_configs(self, morph_box, cib_matrix, driver_index):
        configs = find_consistent_configs(
            morph_box, cib_matrix, driver_index, n_restarts=500, seed=42
        )
        assert len(configs) >= 1
        assert all(c.is_consistent for c in configs)

    def test_sorted_by_score(self, morph_box, cib_matrix, driver_index):
        configs = find_consistent_configs(
            morph_box, cib_matrix, driver_index, n_restarts=500, seed=42
        )
        scores = [c.consistency_score for c in configs]
        assert scores == sorted(scores, reverse=True)

    def test_deterministic_with_seed(self, morph_box, cib_matrix, driver_index):
        c1 = find_consistent_configs(
            morph_box, cib_matrix, driver_index, n_restarts=200, seed=123
        )
        c2 = find_consistent_configs(
            morph_box, cib_matrix, driver_index, n_restarts=200, seed=123
        )
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a.configuration == b.configuration


class TestSelectScenarioSeeds:
    def test_respects_n(self, morph_box, cib_matrix, driver_index):
        configs = find_consistent_configs(
            morph_box, cib_matrix, driver_index, n_restarts=500, seed=42
        )
        seeds = select_scenario_seeds(configs, morph_box, n=2)
        assert len(seeds) <= 2

    def test_empty_input(self, morph_box):
        seeds = select_scenario_seeds([], morph_box, n=5)
        assert seeds == []


class TestInferScenarioType:
    def test_all_optimistic_is_disruptive(self, morph_box):
        config = {d: morph_box.manifestations[d][0] for d in morph_box.drivers}
        assert infer_scenario_type(config, morph_box) == "disruptive"

    def test_all_pessimistic_is_cautionary(self, morph_box):
        config = {d: morph_box.manifestations[d][-1] for d in morph_box.drivers}
        assert infer_scenario_type(config, morph_box) == "cautionary"

    def test_all_middle_is_evolutionary(self, morph_box):
        config = {d: morph_box.manifestations[d][1] for d in morph_box.drivers}
        assert infer_scenario_type(config, morph_box) == "evolutionary"
