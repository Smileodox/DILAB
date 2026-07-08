"""Offline tests for the evidence-grounded pointwise auditor and its hand-off to MCDA.

No live LLM: the pure functions and the JSON->Assessment mapping are exercised directly, and
RAG retrieval is monkeypatched (mirrors tests/test_domain.py / test_landscape_combi.py).
"""
import pytest

from src.config import (
    MCDA_CRITERIA,
    MAX_EVIDENCE_CHUNKS_PER_SCENARIO,
    MAX_EVIDENCE_CHARS_PER_CHUNK,
)
from src.models.drivers import DriverConfidence, DriverOrigin, TechDriver
from src.models.evaluation import Assessment
from src.models.scenarios import DriverAssumption, Scenario, ScenarioType
from src.pipeline import evaluation as ev
from src.pipeline.evaluation import (
    build_cib_context_by_scenario,
    build_scenario_evidence,
    compute_scenario_confidences,
    format_labeled_evidence,
    run_mcda,
    _assessment_from_judge,
    _labels_to_chunk_ids,
)


def _driver(name, chunk_ids, confidence=DriverConfidence.HIGH):
    return TechDriver(name=name, description=name, origin=DriverOrigin.BOM,
                      confidence=confidence, source_chunk_ids=list(chunk_ids))


def _scenario(driver_ids, source_chunk_ids, title="S", narrative="n"):
    return Scenario(
        title=title, narrative=narrative, type=ScenarioType.EVOLUTIONARY,
        perspective="p", source_chunk_ids=list(source_chunk_ids),
        assumptions=[DriverAssumption(driver_id=d, state="x", description=f"assume {d}")
                     for d in driver_ids],
    )


class _FakeCollection:
    """Minimal Chroma-like collection supporting .get(ids=...) for linked-chunk fetch."""
    def __init__(self, docs):
        self._docs = docs  # {chunk_id: (content, source_title)}

    def get(self, ids=None, include=None):
        present = [i for i in (ids or []) if i in self._docs]
        return {
            "ids": present,
            "documents": [self._docs[i][0] for i in present],
            "metadatas": [{"source_title": self._docs[i][1]} for i in present],
        }


# --- 1. grounded scores flow into MCDA -------------------------------------------------

def _grounded_assessments():
    return [
        Assessment(scenario_id="s1", impact=9, probability=5, actionability=7, time_horizon=4,
                   risk_severity=8, confidence=0.9, reasoning="r", grounding_strength="strong",
                   grounding_reason="direct evidence", recommended_actions="act",
                   cib_consistency_strength="strong", cib_consistency_reason="ok"),
        Assessment(scenario_id="s2", impact=4, probability=9, actionability=6, time_horizon=8,
                   risk_severity=3, confidence=0.6, reasoning="r", grounding_strength="moderate"),
        Assessment(scenario_id="s3", impact=6, probability=3, actionability=3, time_horizon=2,
                   risk_severity=6, confidence=0.3, reasoning="r", grounding_strength="weak"),
    ]


class TestGroundedScoresFlowIntoMCDA:
    def test_ranks_and_closeness(self):
        ahp, results = run_mcda(_grounded_assessments())
        assert ahp.is_consistent
        assert sorted(r.rank for r in results) == [1, 2, 3]
        for r in results:
            assert 0 <= r.topsis_closeness <= 1

    def test_criteria_keys_match(self):
        _, results = run_mcda(_grounded_assessments())
        for r in results:
            assert set(r.criteria_scores.keys()) == set(MCDA_CRITERIA)
            assert set(r.weighted_scores.keys()) == set(MCDA_CRITERIA)

    def test_grounding_fields_do_not_disturb_ranking(self):
        # Ranking must depend only on the numeric criteria, not the grounding prose.
        base = _grounded_assessments()
        stripped = [Assessment(scenario_id=a.scenario_id, impact=a.impact, probability=a.probability,
                               actionability=a.actionability, time_horizon=a.time_horizon,
                               risk_severity=a.risk_severity, confidence=a.confidence, reasoning="r")
                    for a in base]
        _, r1 = run_mcda(base)
        _, r2 = run_mcda(stripped)
        assert [r.rank for r in r1] == [r.rank for r in r2]


# --- 2. evidence budget ----------------------------------------------------------------

class TestEvidenceBudget:
    def test_composition_and_cap(self, monkeypatch):
        d1 = _driver("Driver1", ["dc1", "dc2"])
        scen = _scenario([d1.id], ["sc1", "sc2", "sc3"])
        docs = {
            "sc1": ("scenario chunk 1", "src"), "sc2": ("scenario chunk 2", "src"),
            "sc3": ("scenario chunk 3", "src"), "dc1": ("driver chunk 1", "src"),
            "dc2": ("driver chunk 2", "src"),
        }
        collection = _FakeCollection(docs)
        monkeypatch.setattr(ev, "retrieve", lambda collection, query, pool=None, n=5: [
            {"chunk_id": "st1", "content": "stress 1", "source_title": "src"},
            {"chunk_id": "st2", "content": "stress 2", "source_title": "src"},
            {"chunk_id": "st3", "content": "stress 3", "source_title": "src"},
        ])
        pkw = {"domain": "d", "horizon": "2040"}
        evidence = build_scenario_evidence([scen], {d1.id: d1}, collection, pkw)
        chunks = evidence[0]
        ids = [c["chunk_id"] for c in chunks]
        assert len(chunks) <= MAX_EVIDENCE_CHUNKS_PER_SCENARIO
        # 2 scenario + 2 driver + 2 stress (targets), each supply is sufficient
        assert ids[:2] == ["sc1", "sc2"]
        assert set(["dc1", "dc2"]).issubset(ids)
        stress_kept = [i for i in ids if i.startswith("st")]
        assert len(stress_kept) == 2  # capped at TARGET_STRESS_EVIDENCE_CHUNKS

    def test_stress_failure_degrades_gracefully(self, monkeypatch):
        d1 = _driver("Driver1", ["dc1"])
        scen = _scenario([d1.id], ["sc1"])
        collection = _FakeCollection({"sc1": ("s", "src"), "dc1": ("d", "src")})

        def boom(*a, **k):
            raise RuntimeError("no embeddings available")

        monkeypatch.setattr(ev, "retrieve", boom)
        pkw = {"domain": "d", "horizon": "2040"}
        evidence = build_scenario_evidence([scen], {d1.id: d1}, collection, pkw)
        assert [c["chunk_id"] for c in evidence[0]] == ["sc1", "dc1"]


# --- 3. labeled evidence + label -> chunk-id mapping -----------------------------------

class TestEvidenceLabels:
    def test_sequential_labels_and_truncation(self):
        long_content = "A" * (MAX_EVIDENCE_CHARS_PER_CHUNK + 500)
        chunks = [{"chunk_id": "c1", "content": long_content, "source_title": "s"},
                  {"chunk_id": "c2", "content": "short", "source_title": "s"}]
        block, label_map = format_labeled_evidence(chunks)
        assert label_map == {"E1": "c1", "E2": "c2"}
        assert "[E1]" in block and "[E2]" in block
        assert block.count("A") == MAX_EVIDENCE_CHARS_PER_CHUNK  # content truncated

    def test_labels_to_chunk_ids_order_dedup_unknown(self):
        label_map = {"E1": "c1", "E2": "c2", "E3": "c3"}
        assert _labels_to_chunk_ids(["E3", "E1", "E1", "bogus"], label_map) == ["c3", "c1"]
        assert _labels_to_chunk_ids([], label_map) == []


# --- 4. CIB context selection ----------------------------------------------------------

class TestCIBContext:
    def _setup(self):
        a, b, c = _driver("Alpha", []), _driver("Beta", []), _driver("Gamma", [])
        driver_by_id = {a.id: a, b.id: b, c.id: c}
        scen = _scenario([a.id, b.id, c.id], [])
        # rows/cols follow driver_ids order [a, b, c]
        cib_state = {
            "driver_ids": [a.id, b.id, c.id],
            "matrix": [[0, 3, 1],    # a->b = +3 (kept), a->c = +1 (below threshold)
                       [-1, 0, 2],   # b->a = -1 (below threshold), b->c = +2 (kept)
                       [0, 0, 0]],
        }
        return scen, driver_by_id, cib_state

    def test_threshold_and_sort(self):
        scen, driver_by_id, cib_state = self._setup()
        ctx = build_cib_context_by_scenario([scen], driver_by_id, cib_state)[0]
        assert "Alpha promotes Beta (CIB score: +3)" in ctx
        assert "Beta promotes Gamma (CIB score: +2)" in ctx
        assert "Gamma" not in ctx.split("\n")[0]  # strongest first
        assert "score: +1" not in ctx and "-1" not in ctx  # below-threshold excluded

    def test_cap(self, monkeypatch):
        scen, driver_by_id, cib_state = self._setup()
        monkeypatch.setattr(ev, "MAX_CIB_RELATIONSHIPS_PER_SCENARIO", 1)
        ctx = build_cib_context_by_scenario([scen], driver_by_id, cib_state)[0]
        assert ctx == "- Alpha promotes Beta (CIB score: +3)"

    def test_empty_matrix_sentinel(self):
        scen, driver_by_id, _ = self._setup()
        ctx = build_cib_context_by_scenario([scen], driver_by_id, {})[0]
        assert ctx.startswith("No strong CIB relationships")


# --- 5. judge JSON -> Assessment mapping -----------------------------------------------

class TestAssessmentFromJudge:
    def _result(self):
        return {
            "rag_fact_extraction": {"supporting_evidence": ["fact [E1]"], "unsupported_claims": "None"},
            "grounding_strength": "moderate",
            "grounding_reason": "reasonable inference",
            "risks": {"analysis": "supply-chain risk", "severity_score": 7},
            "signals_and_actionability": {"observable_signals": "sig",
                                          "recommended_actions": "invest in X",
                                          "actionability_score": 6, "time_horizon_score": 8},
            "cib_consistency": {"strength": "strong", "reason": "reflects dynamics"},
            "impact_evaluation": {"final_impact_score": 9, "score_boundary_justification": "j"},
            "probability_evaluation": {"final_probability_score": 4, "score_boundary_justification": "j"},
            "source_evidence_labels_used": ["E1", "E3", "bogus"],
        }

    def test_types_and_roundtrip(self):
        scen = _scenario([], [])
        evidence = [{"chunk_id": "c1", "content": "x", "source_title": "s"}]
        a = _assessment_from_judge(self._result(), scen, evidence, {"E1": "c1", "E2": "c2"}, 0.75)
        assert a.impact == 9.0 and a.probability == 4.0
        assert isinstance(a.actionability, float) and a.actionability == 6.0
        assert a.time_horizon == 8.0 and a.risk_severity == 7.0
        assert isinstance(a.recommended_actions, str) and a.recommended_actions == "invest in X"
        assert a.grounding_strength == "moderate"
        assert a.cib_consistency_strength == "strong" and a.cib_consistency_reason == "reflects dynamics"
        assert a.key_risks == "supply-chain risk" and a.early_signals == "sig"
        assert a.confidence == 0.75
        assert a.source_chunk_ids == ["c1"]  # E3/bogus dropped, E1 mapped

    def test_missing_scores_default_to_5(self):
        scen = _scenario([], [])
        evidence = [{"chunk_id": "c1", "content": "x", "source_title": "s"}]
        a = _assessment_from_judge({}, scen, evidence, {}, 0.5)
        assert a.impact == 5.0 and a.probability == 5.0
        assert a.actionability == 5.0 and a.time_horizon == 5.0 and a.risk_severity == 5.0
        # no labels -> falls back to the supplied evidence chunk ids
        assert a.source_chunk_ids == ["c1"]


# --- 6. confidence blend is the current 0.4*driver + 0.6*cib formula -------------------

class TestConfidenceBlend:
    def test_blend_with_consistency(self):
        d = _driver("D", [], confidence=DriverConfidence.HIGH)  # 0.9
        scen = _scenario([d.id], [])
        # cib_conf = 10/10 = 1.0 -> 0.4*0.9 + 0.6*1.0 = 0.96
        conf = compute_scenario_confidences([scen], {d.id: d}, consistency_scores=[10.0])
        assert conf == [0.96]

    def test_blend_without_consistency(self):
        d = _driver("D", [], confidence=DriverConfidence.HIGH)  # 0.9
        scen = _scenario([d.id], [])
        # cib_conf falls back to 0.5 -> 0.4*0.9 + 0.6*0.5 = 0.66 (NOT the mean-only 0.9)
        conf = compute_scenario_confidences([scen], {d.id: d}, consistency_scores=None)
        assert conf == [0.66]
