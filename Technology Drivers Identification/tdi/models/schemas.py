from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    WEAK = "weak_signal"
    STRONG = "strong_signal"
    WELL_ESTABLISHED = "well_established"
    LATENT = "latent_signal"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, description="User foresight query")
    target_year: int = Field(default=2035, ge=2025, le=2050)


class SubCategoryAssignment(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1, default=0.5)
    relationship: str = "coexists_with"
    direction: str = "bidirectional"


class TechnologyCategory(BaseModel):
    """Upper-level technology field (Lee et al. 2022 — Category)."""
    name: str
    confidence: float = Field(ge=0, le=1, default=0.5)
    subcategories: list[SubCategoryAssignment] = []


class IndustryTechnology(BaseModel):
    """Technology within an affected industry that influences or is influenced by M."""
    name: str
    confidence: float = Field(ge=0, le=1, default=0.5)
    relationship: str = "coexists_with"
    direction: str = "bidirectional"


class AffectedIndustry(BaseModel):
    """Industry sector with its own technologies linked to Main Technology (M)."""
    name: str
    confidence: float = Field(ge=0, le=1, default=0.5)
    technologies: list[IndustryTechnology] = []
    is_main: bool = False


class ClassificationResult(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    regulatory_domain: str
    primary_technology: str
    primary_category: str = ""
    main_industry: str = ""
    main_industry_technologies: list[IndustryTechnology] = Field(default_factory=list)
    related_technologies: list[str]
    related_industries: list[str]
    query_intent: str
    technology_categories: list[TechnologyCategory] = Field(default_factory=list)
    affected_industries: list[AffectedIndustry] = Field(default_factory=list)


class ArxivPaper(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    categories: list[str]
    pdf_url: str
    technology: str


class ExtractedEntity(BaseModel):
    entity_type: str
    value: str
    confidence: float = 0.0


class DVIScores(BaseModel):
    diffusion: float = Field(ge=0, le=1)
    visibility: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    composite: float = Field(ge=0, le=1)
    signal_type: SignalType


class TechnologySignal(BaseModel):
    name: str
    dvi: DVIScores
    paper_count: int = 0
    keywords: list[str] = []
    formula_metrics: dict = {}


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str
    properties: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    probability: float = Field(ge=0, le=1)
    edge_class: str = "default"


class PropagationPath(BaseModel):
    source_id: str
    source_label: str
    source_type: str
    target_id: str
    target_label: str
    path_labels: list[str]
    path_node_ids: list[str]
    cascade_probability: float = Field(ge=0, le=1)


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    propagation_paths: list[PropagationPath] = []
    main_technology_id: str = ""
    main_technology_label: str = ""
    main_industry_id: str = ""
    main_industry_label: str = ""


class ImpactTreeNode(BaseModel):
    id: str
    label: str
    node_type: str
    impact_score: float
    children: list["ImpactTreeNode"] = []
    dvi_composite: Optional[float] = None
    growth_rate: Optional[float] = None
    evolution_speed: Optional[str] = None
    evolution_year: Optional[int] = None
    peak_effect_year: Optional[int] = None
    maturity_pct: Optional[float] = None
    target_year: Optional[int] = None
    contributing_technologies: list[str] = Field(default_factory=list)
    relationship_to_main: str = ""
    scenario_cluster_hint: str = ""
    is_scenario_seed: bool = False
    path_id: str = ""
    relation_probability: Optional[float] = None


class ScenarioCluster(str, Enum):
    MAINSTREAM = "mainstream"
    DISRUPTIVE = "disruptive"
    EMERGING = "emerging_opportunity"
    UNCERTAIN = "uncertain"


class FutureScenario(BaseModel):
    id: str
    title: str
    description: str
    cluster: ScenarioCluster
    probability: float
    confidence: float
    visibility_degree: float
    impact_degree: float
    risks: list[str]
    opportunities: list[str]
    supporting_evidence: list[str]
    regulatory_impacts: list[str]
    technological_dependencies: list[str]
    llm_explanation: str = ""


class ForesightResponse(BaseModel):
    query: str
    target_year: int
    classification: ClassificationResult
    classification_json: dict = Field(default_factory=dict)
    papers: list[ArxivPaper]
    signals: list[TechnologySignal]
    knowledge_graph: KnowledgeGraph
    impact_tree: ImpactTreeNode
    scenarios: list[FutureScenario]
    strategic_recommendations: list[str]
    processing_summary: dict = {}


ImpactTreeNode.model_rebuild()
