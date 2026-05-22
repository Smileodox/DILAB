from __future__ import annotations
from pydantic import BaseModel, Field


class Assessment(BaseModel):
    scenario_id: str
    impact: float  # 1-10
    probability: float  # 1-10
    actionability: float = 5.0  # 1-10
    time_horizon: float = 5.0  # 1-10, 10 = imminent
    risk_severity: float = 5.0  # 1-10
    confidence: float  # 0-1, derived from driver confidence
    reasoning: str
    key_risks: str = ""
    early_signals: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)


class AHPWeights(BaseModel):
    criteria: list[str]
    pairwise_matrix: list[list[float]]
    weights: list[float]
    consistency_ratio: float
    is_consistent: bool


class MCDAResult(BaseModel):
    scenario_id: str
    criteria_scores: dict[str, float]
    weighted_scores: dict[str, float]
    topsis_closeness: float
    rank: int
