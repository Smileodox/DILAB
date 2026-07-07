from __future__ import annotations
from pydantic import BaseModel, Field


class Assessment(BaseModel):
    scenario_id: str
    impact: float  # 1-10
    probability: float  # 1-10
    confidence: float  # 0-1, derived from driver confidence
    reasoning: str
    key_risks: str = ""
    early_signals: str = ""
    actionability: str = ""
    grounding_strength: str = ""
    grounding_reason: str = ""
    cib_consistency_strength: str = ""
    cib_consistency_reason: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
