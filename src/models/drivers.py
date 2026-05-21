from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

from src.models.common import _id


class BOMNode(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    description: str = ""
    level: int
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    is_tech_driver: bool = False


class DriverOrigin(str, Enum):
    BOM = "bom"
    TREND = "trend"
    BOTH = "both"


class DriverConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TechDriver(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    description: str
    origin: DriverOrigin
    confidence: DriverConfidence
    bom_node_id: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
    merge_reasoning: str = ""
