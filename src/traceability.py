from __future__ import annotations
import hashlib
import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


def _id() -> str:
    return uuid.uuid4().hex[:12]


def stable_id(*parts: str) -> str:
    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


class SourceType(str, Enum):
    PRODUCT_PAGE = "product_page"
    DATASHEET = "datasheet"
    RESEARCH_PAPER = "research_paper"
    TREND_REPORT = "trend_report"
    REGULATION = "regulation"
    TECH_ARTICLE = "tech_article"


class ContentOrigin(str, Enum):
    FETCHED = "fetched"
    CURATED = "curated"


class KBPool(str, Enum):
    PRODUCT = "product"
    TREND = "trend"


class Source(BaseModel):
    id: str = Field(default_factory=_id)
    url: str = ""
    title: str
    type: SourceType
    pool: KBPool
    content_origin: ContentOrigin = ContentOrigin.CURATED
    retrieved_at: datetime = Field(default_factory=datetime.now)


class Chunk(BaseModel):
    id: str = Field(default_factory=_id)
    source_id: str
    content: str
    section: str = ""
    pool: KBPool


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


class CIBEntry(BaseModel):
    driver_a_id: str
    driver_b_id: str
    impact_score: int  # -3 to +3
    reasoning: str
    source_chunk_ids: list[str] = Field(default_factory=list)


class DriverAssumption(BaseModel):
    driver_id: str
    state: str  # "breakthrough", "steady_progress", "stagnation"
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


class Assessment(BaseModel):
    scenario_id: str
    impact: float  # 1-10
    probability: float  # 1-10
    confidence: float  # 0-1, derived from driver confidence
    reasoning: str
    key_risks: str = ""
    early_signals: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
