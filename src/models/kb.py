from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from src.models.common import _id, KBPool


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
