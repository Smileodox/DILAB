from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field, model_validator

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


class DimensionType(str, Enum):
    HARDWARE = "hardware"
    SOFTWARE = "software"
    REGULATORY = "regulatory"
    MARKET = "market"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGICAL = "technological"
    UNCLASSIFIED = "unclassified"


class AxisRole(str, Enum):
    """Which foresight layer a driver belongs to.

    ``driving``  — an exogenous critical uncertainty (what the world does:
                   regulation, geopolitics, market demand). These DEFINE scenarios.
    ``response`` — an endogenous system/product capability (what our actor's box
                   does: components, architectures). These are OUTCOMES described
                   *within* a scenario, not co-equal scenario axes.

    Mixing the two into one flat morphological field is the category error that
    makes the field collapse onto a couple of latent axes (see structure.py).
    """

    DRIVING = "driving"
    RESPONSE = "response"


# Endogenous (system-response) dimensions vs. exogenous (driving) dimensions.
# `technological` is the EXTERNAL tech-push uncertainty (e.g. AI/ML maturity, new methods) —
# distinct from hardware/software, which are the endogenous product/BOM the study is *about*.
_RESPONSE_DIMENSIONS = {DimensionType.HARDWARE, DimensionType.SOFTWARE}
_DRIVING_DIMENSIONS = {
    DimensionType.REGULATORY,
    DimensionType.MARKET,
    DimensionType.GEOPOLITICAL,
    DimensionType.TECHNOLOGICAL,
}


def derive_axis_role(dimension_type: DimensionType, origin: DriverOrigin) -> AxisRole:
    """Default layer for a driver from its dimension type, falling back on origin.

    Hardware/software → response; regulatory/market/geopolitical/technological → driving. When the
    dimension is unclassified, BOM-origin drivers (decomposed from the product) are
    responses and everything else is treated as a candidate driving uncertainty.
    """
    if dimension_type in _RESPONSE_DIMENSIONS:
        return AxisRole.RESPONSE
    if dimension_type in _DRIVING_DIMENSIONS:
        return AxisRole.DRIVING
    return AxisRole.RESPONSE if origin == DriverOrigin.BOM else AxisRole.DRIVING


class TechDriver(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    description: str
    origin: DriverOrigin
    confidence: DriverConfidence
    dimension_type: DimensionType = DimensionType.UNCLASSIFIED
    axis_role: AxisRole | None = None
    bom_node_id: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
    merge_reasoning: str = ""

    @model_validator(mode="after")
    def _default_axis_role(self) -> "TechDriver":
        # Auto-derive when absent so existing state files (no axis_role) backfill on load.
        if self.axis_role is None:
            self.axis_role = derive_axis_role(self.dimension_type, self.origin)
        return self
