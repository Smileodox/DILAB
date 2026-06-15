from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

from src.models.common import _id


class PersonaScore(BaseModel):
    persona_id: str
    model_used: str = ""
    promoting_score: int = 0
    inhibiting_score: int = 0
    net_score: int = 0
    reasoning: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)


class CIBEntry(BaseModel):
    driver_a_id: str
    driver_b_id: str
    impact_score: int  # -3 to +3
    reasoning: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    persona_scores: list[PersonaScore] = Field(default_factory=list)
    score_std: float = 0.0
    consensus_level: str = "single"  # "strong"|"moderate"|"divergent"|"single"


class DriverAssumption(BaseModel):
    driver_id: str
    manifestation_id: str = ""
    state: str  # manifestation label or legacy generic state
    description: str


class ScenarioType(str, Enum):
    EVOLUTIONARY = "evolutionary"
    DISRUPTIVE = "disruptive"
    CAUTIONARY = "cautionary"
    WILDCARD = "wildcard"


class Scenario(BaseModel):
    id: str = Field(default_factory=_id)
    title: str
    narrative: str
    type: ScenarioType
    perspective: str = ""
    key_tensions: list[str] = Field(default_factory=list)
    assumptions: list[DriverAssumption] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    seed_id: str = ""
    is_fixed_point: bool = True
    coverage_ratio: float = 1.0
