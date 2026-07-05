import pytest
from pydantic import ValidationError

from src.models.evaluation import Assessment, MCDAResult, AHPWeights
from src.models.scenarios import Scenario, ScenarioType
from src.models.drivers import (
    TechDriver, DriverOrigin, DriverConfidence, DimensionType, AxisRole, derive_axis_role,
)
from src.models.llm_responses import CIBResponse, ManifestationResponse, ScenarioResponse


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


def test_dimension_type_enum():
    for t in ["hardware", "software", "regulatory", "market", "geopolitical", "unclassified"]:
        assert DimensionType(t)


def test_driver_dimension_type_default():
    d = TechDriver(name="test", description="desc", origin=DriverOrigin.BOM, confidence=DriverConfidence.HIGH)
    assert d.dimension_type == DimensionType.UNCLASSIFIED


def test_axis_role_enum():
    for r in ["driving", "response"]:
        assert AxisRole(r)


def test_derive_axis_role_by_dimension():
    # Endogenous system capabilities → response.
    assert derive_axis_role(DimensionType.HARDWARE, DriverOrigin.BOM) == AxisRole.RESPONSE
    assert derive_axis_role(DimensionType.SOFTWARE, DriverOrigin.TREND) == AxisRole.RESPONSE
    # Exogenous world uncertainties → driving.
    assert derive_axis_role(DimensionType.REGULATORY, DriverOrigin.TREND) == AxisRole.DRIVING
    assert derive_axis_role(DimensionType.MARKET, DriverOrigin.TREND) == AxisRole.DRIVING
    assert derive_axis_role(DimensionType.GEOPOLITICAL, DriverOrigin.TREND) == AxisRole.DRIVING


def test_derive_axis_role_unclassified_falls_back_on_origin():
    assert derive_axis_role(DimensionType.UNCLASSIFIED, DriverOrigin.BOM) == AxisRole.RESPONSE
    assert derive_axis_role(DimensionType.UNCLASSIFIED, DriverOrigin.TREND) == AxisRole.DRIVING
    assert derive_axis_role(DimensionType.UNCLASSIFIED, DriverOrigin.BOTH) == AxisRole.DRIVING


def test_driver_axis_role_auto_derived():
    hw = TechDriver(name="ADC", description="d", origin=DriverOrigin.BOM,
                    confidence=DriverConfidence.MEDIUM, dimension_type=DimensionType.HARDWARE)
    reg = TechDriver(name="IMT harmonization", description="d", origin=DriverOrigin.TREND,
                     confidence=DriverConfidence.MEDIUM, dimension_type=DimensionType.REGULATORY)
    assert hw.axis_role == AxisRole.RESPONSE
    assert reg.axis_role == AxisRole.DRIVING


def test_driver_axis_role_explicit_preserved():
    d = TechDriver(name="x", description="d", origin=DriverOrigin.BOM,
                   confidence=DriverConfidence.LOW, dimension_type=DimensionType.HARDWARE,
                   axis_role=AxisRole.DRIVING)
    assert d.axis_role == AxisRole.DRIVING


def test_driver_axis_role_backfilled_from_dict():
    # Existing state files (merge_state.json) have no axis_role — it must backfill on load.
    raw = {"name": "IMT", "description": "d", "origin": "trend",
           "confidence": "medium", "dimension_type": "regulatory"}
    d = TechDriver.model_validate(raw)
    assert d.axis_role == AxisRole.DRIVING


class TestCIBResponse:
    def test_valid_response(self):
        r = CIBResponse(
            relationship_analysis="test",
            inhibiting_score=2, inhibiting_reasoning="conflict",
            promoting_score=1, promoting_reasoning="synergy",
        )
        assert r.inhibiting_score == 2
        assert r.promoting_score == 1

    def test_clamping(self):
        r = CIBResponse(inhibiting_score=5, promoting_score=-1)
        assert r.inhibiting_score == 3
        assert r.promoting_score == 0

    def test_from_dict(self):
        raw = {
            "relationship_analysis": "test",
            "inhibiting_score": 2,
            "inhibiting_reasoning": "conflict",
            "promoting_score": 1,
            "promoting_reasoning": "synergy",
            "source_chunk_ids_used": ["c1"],
        }
        r = CIBResponse.model_validate(raw)
        assert r.source_chunk_ids_used == ["c1"]


class TestManifestationResponse:
    def test_valid(self):
        r = ManifestationResponse(manifestations=[
            {"label": "test", "description": "desc"},
        ])
        assert len(r.manifestations) == 1

    def test_empty_fails(self):
        with pytest.raises(ValidationError):
            ManifestationResponse(manifestations=[])


class TestScenarioResponse:
    def test_valid(self):
        r = ScenarioResponse(title="Test", narrative="A long narrative")
        assert r.title == "Test"
        assert r.key_tensions == []
