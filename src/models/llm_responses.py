"""Pydantic models for validating raw LLM JSON responses.

Each model corresponds to a specific prompt's expected output structure.
Used by validated_chat_json() to catch malformed LLM outputs early.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CIBResponse(BaseModel):
    relationship_analysis: str = ""
    inhibiting_score: int = Field(ge=0, le=3)
    inhibiting_reasoning: str = ""
    promoting_score: int = Field(ge=0, le=3)
    promoting_reasoning: str = ""
    source_chunk_ids_used: list[str] = Field(default_factory=list)

    @field_validator("inhibiting_score", "promoting_score", mode="before")
    @classmethod
    def clamp_score(cls, v: object) -> int:
        try:
            return max(0, min(3, int(v)))
        except (TypeError, ValueError):
            return 0


class ManifestationItem(BaseModel):
    label: str
    description: str
    plausibility: str = "medium"
    grounding: str = ""


class ManifestationResponse(BaseModel):
    manifestations: list[ManifestationItem] = Field(min_length=1)
    source_chunk_ids_used: list[str] = Field(default_factory=list)


class ScenarioResponse(BaseModel):
    title: str
    narrative: str
    perspective: str = ""
    key_changes: list[str] = Field(default_factory=list)
    key_tensions: list[str] = Field(default_factory=list)
    source_chunk_ids_used: list[str] = Field(default_factory=list)


class AssessmentItem(BaseModel):
    scenario_index: int = 0
    impact: float = Field(ge=1, le=10)
    probability: float = Field(ge=1, le=10)
    actionability: float = Field(default=5.0, ge=1, le=10)
    time_horizon: float = Field(default=5.0, ge=1, le=10)
    risk_severity: float = Field(default=5.0, ge=1, le=10)
    reasoning: str = ""
    key_risks: str = ""
    early_signals: str = ""
    source_chunk_ids_used: list[str] = Field(default_factory=list)

    @field_validator("impact", "probability", "actionability", "time_horizon", "risk_severity", mode="before")
    @classmethod
    def clamp_score(cls, v: object) -> float:
        try:
            return max(1.0, min(10.0, float(v)))
        except (TypeError, ValueError):
            return 5.0


class AssessmentResponse(BaseModel):
    assessments: list[AssessmentItem] = Field(min_length=1)


class StrategicFramingResponse(BaseModel):
    critical_uncertainties: list[dict] = Field(default_factory=list)
    no_regret_moves: list[dict] = Field(default_factory=list)
    scenario_strategy: list[dict] = Field(default_factory=list)
    recommended_priority: dict = Field(default_factory=dict)
