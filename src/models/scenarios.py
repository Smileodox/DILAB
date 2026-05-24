from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

from src.models.common import _id


class CIBEntry(BaseModel):
    driver_a_id: str
    driver_b_id: str
    impact_score: int  # -3 to +3
    reasoning: str
    source_chunk_ids: list[str] = Field(default_factory=list)


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
