import numpy as np
import pytest

from src.pipeline.evaluation import compute_ahp_weights, compute_topsis, run_mcda
from src.models.evaluation import Assessment
from src.config import MCDA_PAIRWISE_DEFAULT, MCDA_CRITERIA


class TestAHP:
    def test_identity_matrix_equal_weights(self):
        n = 4
        matrix = [[1.0] * n for _ in range(n)]
        result = compute_ahp_weights(matrix, criteria=[f"c{i}" for i in range(n)])
        for w in result.weights:
            assert abs(w - 1 / n) < 1e-6
        assert result.consistency_ratio == 0.0
        assert result.is_consistent

    def test_known_3x3(self):
        matrix = [[1, 3, 5], [1/3, 1, 2], [1/5, 1/2, 1]]
        result = compute_ahp_weights(matrix, criteria=["a", "b", "c"])
        assert abs(sum(result.weights) - 1.0) < 1e-6
        assert result.weights[0] > result.weights[1] > result.weights[2]
        assert result.is_consistent

    def test_inconsistent_matrix(self):
        matrix = [[1, 9, 1], [1/9, 1, 9], [1, 1/9, 1]]
        result = compute_ahp_weights(matrix, criteria=["a", "b", "c"], cr_threshold=0.10)
        assert not result.is_consistent

    def test_default_5x5(self):
        result = compute_ahp_weights(MCDA_PAIRWISE_DEFAULT, criteria=MCDA_CRITERIA)
        assert abs(sum(result.weights) - 1.0) < 1e-6
        assert result.is_consistent
        assert len(result.weights) == 5
        # Impact should have highest weight
        impact_idx = MCDA_CRITERIA.index("impact")
        assert result.weights[impact_idx] == max(result.weights)

    def test_reciprocal_property(self):
        m = MCDA_PAIRWISE_DEFAULT
        n = len(m)
        for i in range(n):
            for j in range(n):
                assert abs(m[i][j] * m[j][i] - 1.0) < 1e-6, f"a[{i}][{j}] * a[{j}][{i}] != 1"

    def test_weights_sum_to_one(self):
        result = compute_ahp_weights(MCDA_PAIRWISE_DEFAULT, criteria=MCDA_CRITERIA)
        assert abs(sum(result.weights) - 1.0) < 1e-6

    def test_2x2_no_consistency_issue(self):
        result = compute_ahp_weights([[1, 5], [1/5, 1]], criteria=["a", "b"])
        assert result.consistency_ratio == 0.0
        assert result.is_consistent


class TestTOPSIS:
    def test_dominant_scenario(self):
        dm = np.array([[10, 10, 10], [1, 1, 1], [5, 5, 5]])
        weights = np.array([1/3, 1/3, 1/3])
        closeness = compute_topsis(dm, weights)
        assert closeness[0] == max(closeness)
        assert abs(closeness[0] - 1.0) < 0.01

    def test_worst_scenario(self):
        dm = np.array([[10, 10, 10], [1, 1, 1], [5, 5, 5]])
        weights = np.array([1/3, 1/3, 1/3])
        closeness = compute_topsis(dm, weights)
        assert closeness[1] == min(closeness)
        assert abs(closeness[1] - 0.0) < 0.01

    def test_ranking_order(self):
        dm = np.array([[9, 8, 7], [6, 5, 4], [3, 2, 1]])
        weights = np.array([0.5, 0.3, 0.2])
        closeness = compute_topsis(dm, weights)
        assert closeness[0] > closeness[1] > closeness[2]

    def test_closeness_range(self):
        dm = np.array([[8, 3, 7, 9, 2], [5, 6, 4, 3, 8], [2, 9, 1, 6, 5], [7, 2, 8, 4, 3]])
        weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])
        closeness = compute_topsis(dm, weights)
        for c in closeness:
            assert 0 <= c <= 1

    def test_equal_scenarios(self):
        dm = np.array([[5, 5], [5, 5]])
        weights = np.array([0.5, 0.5])
        closeness = compute_topsis(dm, weights)
        assert abs(closeness[0] - closeness[1]) < 1e-6


class TestMCDAIntegration:
    def _make_assessments(self) -> list[Assessment]:
        return [
            Assessment(scenario_id="s1", impact=9, probability=5, actionability=7,
                       time_horizon=4, risk_severity=8, confidence=0.9, reasoning="high impact"),
            Assessment(scenario_id="s2", impact=4, probability=9, actionability=6,
                       time_horizon=8, risk_severity=3, confidence=0.6, reasoning="high prob"),
            Assessment(scenario_id="s3", impact=6, probability=3, actionability=3,
                       time_horizon=2, risk_severity=6, confidence=0.3, reasoning="moderate"),
        ]

    def test_run_mcda_structure(self):
        ahp, results = run_mcda(self._make_assessments())
        assert ahp.is_consistent
        assert len(results) == 3
        ranks = sorted([r.rank for r in results])
        assert ranks == [1, 2, 3]

    def test_run_mcda_closeness_range(self):
        _, results = run_mcda(self._make_assessments())
        for r in results:
            assert 0 <= r.topsis_closeness <= 1

    def test_run_mcda_criteria_scores(self):
        _, results = run_mcda(self._make_assessments())
        for r in results:
            assert set(r.criteria_scores.keys()) == set(MCDA_CRITERIA)
            assert set(r.weighted_scores.keys()) == set(MCDA_CRITERIA)

    def test_custom_pairwise_matrix(self):
        equal = [[1.0] * 5 for _ in range(5)]
        ahp, results = run_mcda(self._make_assessments(), pairwise_matrix=equal)
        for w in ahp.weights:
            assert abs(w - 0.2) < 1e-6
