from src.models.evaluation import Assessment, MCDAResult, AHPWeights
from src.models.scenarios import Scenario, ScenarioType
from src.models.drivers import TechDriver, DriverOrigin, DriverConfidence


def test_assessment_all_criteria():
    a = Assessment(
        scenario_id="test", impact=8, probability=6, actionability=7,
        time_horizon=4, risk_severity=9, confidence=0.8, reasoning="ok",
    )
    assert a.actionability == 7
    assert a.time_horizon == 4
    assert a.risk_severity == 9


def test_assessment_defaults():
    a = Assessment(scenario_id="test", impact=5, probability=5, confidence=0.5, reasoning="ok")
    assert a.actionability == 5.0
    assert a.time_horizon == 5.0
    assert a.risk_severity == 5.0
    assert a.key_risks == ""
    assert a.source_chunk_ids == []


def test_assessment_from_fixture(sample_assessments):
    for a in sample_assessments:
        assert 1 <= a.impact <= 10
        assert 1 <= a.probability <= 10
        assert 0 <= a.confidence <= 1


def test_mcda_result():
    r = MCDAResult(
        scenario_id="s1",
        criteria_scores={"impact": 8, "probability": 6},
        weighted_scores={"impact": 2.4, "probability": 1.2},
        topsis_closeness=0.73,
        rank=1,
    )
    assert 0 <= r.topsis_closeness <= 1
    assert r.rank == 1


def test_ahp_weights():
    w = AHPWeights(
        criteria=["a", "b"], pairwise_matrix=[[1, 2], [0.5, 1]],
        weights=[0.667, 0.333], consistency_ratio=0.0, is_consistent=True,
    )
    assert w.is_consistent
    assert len(w.weights) == 2


def test_scenario_from_fixture(sample_scenarios):
    for s in sample_scenarios:
        assert s.type in ScenarioType
        assert len(s.assumptions) > 0
        assert s.title


def test_scenario_types():
    for t in ["evolutionary", "disruptive", "cautionary", "wildcard"]:
        assert ScenarioType(t)


def test_driver_from_fixture(sample_drivers):
    for d in sample_drivers:
        assert d.origin in DriverOrigin
        assert d.confidence in DriverConfidence
        assert d.name


def test_driver_enums():
    for o in ["bom", "trend", "both"]:
        assert DriverOrigin(o)
    for c in ["high", "medium", "low"]:
        assert DriverConfidence(c)
