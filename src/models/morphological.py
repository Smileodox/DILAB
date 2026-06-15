from __future__ import annotations
from pydantic import BaseModel, Field

from src.models.common import _id


class DriverManifestation(BaseModel):
    id: str = Field(default_factory=_id)
    driver_id: str
    label: str
    description: str
    plausibility: str  # "high" | "medium" | "low"
    source_chunk_ids: list[str] = Field(default_factory=list)


class MorphologicalBox(BaseModel):
    drivers: list[str]
    manifestations: dict[str, list[str]]
    all_manifestations: list[DriverManifestation]


class ConsistencyResult(BaseModel):
    id: str = Field(default_factory=_id)
    configuration: dict[str, str]
    consistency_score: float
    is_consistent: bool
    scenario_type: str = "evolutionary"
    frequency: int = 1
    is_fixed_point: bool = True
    parent_fixed_point_id: str = ""
    flipped_driver_id: str = ""
