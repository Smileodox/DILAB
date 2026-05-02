from pydantic import BaseModel, Field


class DriverState(BaseModel):
    name: str
    description: str


class Driver(BaseModel):
    name: str
    description: str
    states: list[DriverState]


class CrossImpactRating(BaseModel):
    target_driver: str
    target_state: str
    impact: int = Field(ge=-3, le=3)
    rationale: str


class SourceStateImpacts(BaseModel):
    source_driver: str
    source_state: str
    impacts: list[CrossImpactRating]


class ExtractedDriver(BaseModel):
    name: str
    description: str
    steep_category: str = Field(description="STEEP category: Social, Technological, Economic, Environmental, or Political")
    trl_low: int = Field(ge=1, le=9, description="Lower bound of Technology Readiness Level estimate")
    trl_high: int = Field(ge=1, le=9, description="Upper bound of Technology Readiness Level estimate")
    source_papers: list[str] = Field(description="Titles of arxiv papers that mention this driver")


class DriverExtractionResult(BaseModel):
    drivers: list[ExtractedDriver]


# --- Observable Pipeline Models (poc2c) ---


class SourceEvidence(BaseModel):
    paper_title: str
    paper_id: str
    chunk_text: str = Field(description="Exact verbatim text excerpt from the paper that supports this driver")
    relevance: str = Field(description="1-2 sentence explanation of how this passage supports the driver")


class ObservableDriver(BaseModel):
    name: str
    description: str
    steep_category: str = Field(description="STEEP category: Social, Technological, Economic, Environmental, or Political")
    trl_low: int = Field(ge=1, le=9)
    trl_high: int = Field(ge=1, le=9)
    evidence: list[SourceEvidence] = Field(min_length=1, description="Source passages supporting this driver. Must include exact quotes.")
    extraction_rationale: str = Field(description="Why this is a significant technology driver for R&S spectrum monitoring/T&M")


class ObservableDriverExtractionResult(BaseModel):
    drivers: list[ObservableDriver]


class AtomicClaim(BaseModel):
    claim: str = Field(description="A single atomic factual statement")
    supported: bool
    supporting_quote: str | None = Field(default=None, description="Exact quote from source evidence, or null if unsupported")
    source_paper_title: str | None = Field(default=None)


class FaithfulnessResult(BaseModel):
    driver_name: str
    claims: list[AtomicClaim]
    faithfulness_score: float = Field(ge=0.0, le=1.0)
    unsupported_claims_summary: str


class SurpriseAssessment(BaseModel):
    driver_name: str
    surprise_rating: int = Field(ge=1, le=5, description="1=expected, 3=somewhat surprising, 5=genuine blind spot")
    explanation: str
    rs_relevance: str = Field(description="Specific implications for R&S spectrum monitoring, T&M, or defense business")
    known_by_rs: bool = Field(description="Whether R&S likely already tracks this driver")
    contrarian_angle: str | None = Field(default=None, description="Non-obvious angle making this driver more important than it appears")


class RetrievalRecord(BaseModel):
    query: str
    chunk_node_id: str
    chunk_text_preview: str = Field(description="First 200 chars of chunk")
    paper_title: str
    paper_id: str
    similarity_score: float


class DriverAuditReport(BaseModel):
    driver: ObservableDriver
    retrieval_records: list[RetrievalRecord]
    faithfulness: FaithfulnessResult
    surprise_geometric: float
    surprise_llm: SurpriseAssessment
