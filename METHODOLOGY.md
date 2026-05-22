# Methodology: AI-Driven Strategic Technology Foresight

## Overview

This prototype implements a hybrid technology foresight pipeline for Rohde & Schwarz regulatory frequency monitoring products. It combines bottom-up product analysis with top-down trend scanning to identify technology drivers, evaluate their cross-impacts, and generate future scenarios — all with end-to-end source traceability.

## Pipeline

### 1. Knowledge Base Construction
Two separate retrieval pools are built from curated sources:
- **KB-Product**: R&S product pages and datasheets (ESMD, ESMW, UMS300)
- **KB-Trends**: Research papers, trend reports, ITU-adjacent literature

Sources are chunked, embedded (Azure OpenAI `text-embedding-3-small`), and stored in ChromaDB with pool tags and source metadata for downstream traceability.

### 2. Bottom-Up: BOM Decomposition
Starting from a target product (R&S ESMW), the system iteratively decomposes the Bill of Materials level by level (Product → Subsystem → Component → Technology). Each decomposition step uses focused RAG retrieval from KB-Product (max 3 chunks) to stay grounded. Leaf nodes are classified as technology drivers or passive components.

### 3. Top-Down: Trend Scanning
Five thematic queries scan KB-Trends for technology megatrends relevant to spectrum monitoring (AI/ML, quantum sensing, 6G, space-based monitoring, edge computing). Each trend is assessed for domain-specific impact. Only high/medium-impact trends are retained as trend-derived drivers.

### 4. Driver Merge & Confidence Scoring
BOM drivers and trend drivers are mapped onto each other via LLM-assisted matching:
- **Validated** (both sources) → high confidence
- **Incremental** (BOM-only) → medium confidence
- **Speculative** (trend-only) → low confidence

Embedding-based cosine similarity consolidates near-duplicate drivers to keep the list manageable. ID validation and forgotten-driver recovery guard against LLM hallucination.

### 5. Cross-Impact Balance (CIB) Matrix
All driver pairs are evaluated pairwise: "If Driver A breaks through, how does it affect Driver B?" To counteract LLM positivity bias, a **split-scoring** approach is used — the model must separately score promoting factors (0–3) and inhibiting factors (0–3). The net score (promoting minus inhibiting) populates the CIB matrix. This produces a realistic distribution including zero and low-positive scores, rather than uniformly high values.

### 6. Scenario Generation
Four scenarios are constructed from different driver-state combinations:
- 2 evolutionary (validated/incremental drivers, breakthrough vs. steady progress)
- 2 disruptive (speculative drivers, breakthrough vs. mixed stagnation/disruption)

A **CIB consistency check** validates that driver-state assumptions don't contradict the cross-impact matrix (e.g., if A="breakthrough" and CIB[A→B] is strongly negative, B cannot also be "breakthrough"). Each scenario is generated with RAG-grounded context to maintain source traceability.

### 7. Multi-Criteria Scenario Assessment (MCDA)
All scenarios are evaluated in a single **batch prompt with forced ranking** across five criteria:
- **Impact** (1–10): How transformative the scenario is for R&S products and the domain
- **Probability** (1–10): Likelihood of materialization by 2035
- **Actionability** (1–10): How much R&S can proactively prepare or influence the outcome
- **Time Horizon** (1–10, 10 = imminent): How soon effects will be felt
- **Risk Severity** (1–10): Severity of consequences if R&S fails to prepare

Confidence is computed from the mean driver confidence of each scenario's assumptions.

The raw scores are then processed through a two-stage **Multi-Criteria Decision Analysis (MCDA)**:

1. **AHP (Analytic Hierarchy Process)** derives criterion weights from a pairwise comparison matrix. Each pair of criteria is compared on Saaty's 1–9 scale (how much more important is criterion A vs. B?). The eigenvector of the comparison matrix yields normalized weights, and a consistency ratio (CR < 0.10) validates that the comparisons are logically coherent. Default weights encode: Impact > Probability ≥ Risk Severity > Time Horizon > Actionability.

2. **TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution)** ranks scenarios using the AHP-weighted criteria. The decision matrix is vector-normalized, weighted, then each scenario's Euclidean distance to the ideal best and ideal worst solutions is computed. The closeness coefficient C = D⁻/(D⁺+D⁻) produces a single composite score (0–1) per scenario, enabling a definitive ranking.

Results are visualized as an MCDA ranking bar chart, a criteria radar overlay, and the classic Impact vs. Probability scatter with MCDA rank annotations.

## Key Design Decisions

**Traceability**: Every artifact (driver, CIB entry, scenario, assessment) carries `source_chunk_ids` linking back to original KB sources. The final report traces each scenario through its assumptions, drivers, merge reasoning, and source documents.

**LLM Bias Mitigation**: Two techniques address the known positivity/sycophancy bias of LLMs:
1. CIB split-scoring forces explicit inhibition scores rather than letting the model optimize away negative relationships
2. Batch assessment with forced ranking prevents all scenarios from clustering at the same score

**MCDA over simple scoring**: A 2D Impact×Probability matrix misses strategically important dimensions (actionability, urgency, risk). AHP+TOPSIS was chosen over simpler weighted-sum because TOPSIS handles inter-criteria tradeoffs more robustly and produces a single composite score that accounts for distance to both the ideal and anti-ideal solution.

**Focused RAG**: Following the principle of lean prompts, each LLM call retrieves only 3–5 relevant chunks rather than dumping the entire knowledge base, improving both quality and traceability.

## Tech Stack

- **LLM**: Azure OpenAI gpt-4.1-mini (chat + JSON mode)
- **Embeddings**: Azure OpenAI text-embedding-3-small
- **Vector Store**: ChromaDB (local, persistent)
- **Data Models**: Pydantic v2 (type-safe traceability chain)
- **Orchestration**: Jupyter Notebooks (sequential, state passed via JSON)
- **Package Management**: uv
