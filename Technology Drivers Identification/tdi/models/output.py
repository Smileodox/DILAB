"""Pydantic models for Technology Drivers Identification RAG output."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0.0"
PIPELINE_NAME = "technology_drivers_identification"


class IdentificationInput(BaseModel):
    query: str = Field(..., min_length=3)
    target_year: int = Field(default=2035, ge=2025, le=2050)


class TechnologyIndustryClassification(BaseModel):
    """Step 1 — LLM TOD taxonomy + industry mapping."""
    regulatory_domain: str
    primary_technology: str
    primary_category: str = ""
    main_industry: str = ""
    query_intent: str = ""
    related_technologies: list[str] = Field(default_factory=list)
    related_industries: list[str] = Field(default_factory=list)
    technology_categories: list[dict[str, Any]] = Field(default_factory=list)
    affected_industries: list[dict[str, Any]] = Field(default_factory=list)
    main_industry_technologies: list[dict[str, Any]] = Field(default_factory=list)
    llm_classification_raw: dict[str, Any] = Field(default_factory=dict)


class ResearchEvidence(BaseModel):
    """Step 2–3 — arXiv papers, NLP entities, keywords."""
    papers: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class SignalClassification(BaseModel):
    """Step 4 — DVI weak/strong/latent signal analysis per technology."""
    framework: str = "Wang & Zhu (2026) MLWS-TF DVI"
    signals: list[dict[str, Any]] = Field(default_factory=list)
    by_signal_type: dict[str, list[str]] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphSection(BaseModel):
    """Step 5 — Technology–industry–regulation graph with ML edge probabilities."""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    propagation_paths: list[dict[str, Any]] = Field(default_factory=list)
    main_technology_id: str = ""
    main_technology_label: str = ""
    main_industry_id: str = ""
    main_industry_label: str = ""
    statistics: dict[str, Any] = Field(default_factory=dict)


class ImpactTreeSection(BaseModel):
    """Step 6 — Technology evolution paths to target year."""
    tree: dict[str, Any] = Field(default_factory=dict)
    evolution_paths: list[dict[str, Any]] = Field(default_factory=list)
    scenario_seeds: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)


class RagDocument(BaseModel):
    """Single chunk for vector-store / LLM context retrieval."""
    id: str
    section: str
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagContext(BaseModel):
    """Pre-built text chunks for downstream scenario LLM (RAG)."""
    documents: list[RagDocument] = Field(default_factory=list)
    consolidated_narrative: str = ""


class TechnologyDriversIdentificationOutput(BaseModel):
    """
    Complete JSON artifact from Technology Drivers Identification (pipeline step 1).
    Intended as structured context for scenario generation and other foresight LLM tasks.
    """
    schema_version: str = SCHEMA_VERSION
    pipeline: str = PIPELINE_NAME
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    input: IdentificationInput
    technology_industry_classification: TechnologyIndustryClassification
    research_evidence: ResearchEvidence
    signal_classification: SignalClassification
    knowledge_graph: KnowledgeGraphSection
    impact_tree: ImpactTreeSection
    processing_summary: dict[str, Any] = Field(default_factory=dict)
    rag_context: RagContext = Field(default_factory=RagContext)
