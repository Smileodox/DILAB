from __future__ import annotations
from pydantic import BaseModel, Field


class Assessment(BaseModel):
    scenario_id: str
    impact: float  # 1-10
    probability: float  # 1-10
    actionability: float = 5.0  # 1-10  (MCDA criterion — numeric; prose lives in recommended_actions)
    time_horizon: float = 5.0  # 1-10, 10 = imminent
    risk_severity: float = 5.0  # 1-10
    confidence: float  # 0-1, derived from driver confidence
    reasoning: str
    key_risks: str = ""
    early_signals: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    # --- evidence-grounding / audit (from the pointwise auditor) ---
    recommended_actions: str = ""       # concrete actions the actor could take now
    grounding_strength: str = ""        # strong|moderate|weak — how evidence-backed the assessment is
    grounding_reason: str = ""
    cib_consistency_strength: str = ""  # strong|moderate|weak|not_applicable
    cib_consistency_reason: str = ""


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
