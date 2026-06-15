from src.pipeline.merge import normalize_name, build_unified_list
from src.models.drivers import TechDriver, DriverOrigin, DriverConfidence


class TestNormalizeName:
    def test_basic(self):
        assert normalize_name("AI/ML Processing") == "ai/ml processing"

    def test_strips_parentheses(self):
        assert normalize_name("Quantum Sensing (Rydberg Atoms)") == "quantum sensing"

    def test_collapses_whitespace(self):
        assert normalize_name("  edge   computing  ") == "edge computing"

    def test_empty(self):
        assert normalize_name("") == ""

    def test_preserves_hyphens_slashes(self):
        assert normalize_name("AI/ML-based Processing") == "ai/ml-based processing"


def _driver(name, origin, confidence, **kw):
    return TechDriver(
        id=f"drv_{name.replace(' ', '_').lower()}",
        name=name,
        description=f"desc of {name}",
        origin=origin,
        confidence=confidence,
        source_chunk_ids=kw.get("source_chunk_ids", []),
    )


class TestBuildUnifiedList:
    def test_matched_driver_gets_high_confidence(self):
        bom = [_driver("Quantum Sensors", DriverOrigin.BOM, DriverConfidence.MEDIUM, source_chunk_ids=["c1"])]
        trend = [_driver("Quantum RF", DriverOrigin.TREND, DriverConfidence.LOW, source_chunk_ids=["c2"])]
        merge_result = {
            "matches": [{"bom_driver_index": 0, "trend_driver_index": 0,
                         "unified_name": "Quantum Sensing", "reasoning": "same tech"}],
            "bom_only": [],
            "trend_only": [],
        }
        result = build_unified_list(merge_result, bom, trend)
        assert len(result) == 1
        assert result[0].confidence == DriverConfidence.HIGH
        assert result[0].origin == DriverOrigin.BOTH

    def test_bom_only_gets_medium_confidence(self):
        bom = [_driver("SDR Tech", DriverOrigin.BOM, DriverConfidence.MEDIUM)]
        merge_result = {"matches": [], "bom_only": [0], "trend_only": []}
        result = build_unified_list(merge_result, bom, [])
        assert len(result) == 1
        assert result[0].confidence == DriverConfidence.MEDIUM

    def test_trend_only_gets_medium_confidence(self):
        trend = [_driver("6G Networks", DriverOrigin.TREND, DriverConfidence.LOW)]
        merge_result = {"matches": [], "bom_only": [], "trend_only": [0]}
        result = build_unified_list(merge_result, [], trend)
        assert len(result) == 1
        # Trend-only drivers get MEDIUM: external regulatory/environmental forces
        # deserve equal footing with unvalidated BOM components in consolidation.
        assert result[0].confidence == DriverConfidence.MEDIUM

    def test_source_chunks_merged_on_match(self):
        bom = [_driver("Test BOM", DriverOrigin.BOM, DriverConfidence.MEDIUM, source_chunk_ids=["c1", "c2"])]
        trend = [_driver("Test Trend", DriverOrigin.TREND, DriverConfidence.LOW, source_chunk_ids=["c3"])]
        merge_result = {
            "matches": [{"bom_driver_index": 0, "trend_driver_index": 0,
                         "unified_name": "Test", "reasoning": "merged"}],
            "bom_only": [],
            "trend_only": [],
        }
        result = build_unified_list(merge_result, bom, trend)
        assert set(result[0].source_chunk_ids) == {"c1", "c2", "c3"}

    def test_mixed_merge_result(self):
        bom = [
            _driver("A", DriverOrigin.BOM, DriverConfidence.MEDIUM),
            _driver("B", DriverOrigin.BOM, DriverConfidence.MEDIUM),
        ]
        trend = [_driver("C", DriverOrigin.TREND, DriverConfidence.LOW)]
        merge_result = {
            "matches": [{"bom_driver_index": 0, "trend_driver_index": 0,
                         "unified_name": "A+C", "reasoning": "match"}],
            "bom_only": [1],
            "trend_only": [],
        }
        result = build_unified_list(merge_result, bom, trend)
        assert len(result) == 2
        confs = {r.confidence for r in result}
        assert DriverConfidence.HIGH in confs
        assert DriverConfidence.MEDIUM in confs
