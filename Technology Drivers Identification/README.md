# Technology Drivers Identification

**Pipeline step 1** of the Tech Fore AI foresight system. Takes a query and produces a **structured JSON artifact** with all driver-analysis outputs, plus **RAG-ready text chunks** for downstream LLM scenario generation.

This module is designed so the full foresight UI becomes step 2+ (scenarios, recommendations), while step 1 exports a portable knowledge bundle.

## What it produces

| Section | Source pipeline step | Contents |
|---------|---------------------|----------|
| `technology_industry_classification` | LLM + TOD taxonomy | Domain, primary tech (M), industries, categories |
| `research_evidence` | arXiv + NLP | Papers, entities, keywords |
| `signal_classification` | DVI analyzer | Per-tech DVI scores, weak/strong/latent types |
| `knowledge_graph` | KG builder | Nodes, edges, propagation paths, probabilities |
| `impact_tree` | Impact tree builder | Full tree, evolution paths, scenario seeds |
| `rag_context` | Auto-generated | 5 document chunks + `consolidated_narrative` for LLM RAG |

## Folder structure

```
Technology Drivers Identification/
├── README.md
├── run.py                    # CLI — writes JSON to output/
├── schema/
│   └── technology_drivers_output.schema.json
├── output/                   # Generated JSON files (gitignored)
└── src/
    ├── pipeline.py           # Main orchestrator (steps 1–6)
    ├── models.py             # Pydantic output schema
    ├── rag_builder.py        # RAG text chunk builder
    ├── serializers.py        # Tree/graph flattening
    └── path_utils.py         # Backend import helper
```

## Quick start (CLI)

From project root, with backend venv activated and `OPENROUTER_API_KEY` in `.env`:

```bash
cd backend && source venv/bin/activate
cd "../Technology Drivers Identification"

python run.py "Regulatory Spectrum Monitoring" --year 2035
python run.py "Drone Warfare" -o output/drone_warfare_2035.json
```

Output: `output/<slug>_<year>.json`

## API endpoint

The main FastAPI backend exposes the same pipeline:

```http
POST /api/drivers-identification
Content-Type: application/json

{
  "query": "Drone Warfare",
  "target_year": 2035
}
```

Returns the full `TechnologyDriversIdentificationOutput` JSON (no scenarios or recommendations).

## JSON top-level shape

```json
{
  "schema_version": "1.0.0",
  "pipeline": "technology_drivers_identification",
  "generated_at": "2026-06-26T12:00:00+00:00",
  "input": { "query": "...", "target_year": 2035 },
  "technology_industry_classification": { ... },
  "research_evidence": { ... },
  "signal_classification": { ... },
  "knowledge_graph": { ... },
  "impact_tree": { ... },
  "processing_summary": { ... },
  "rag_context": {
    "documents": [
      { "id": "tech_industry_classification", "section": "...", "title": "...", "content": "..." },
      { "id": "research_evidence", ... },
      { "id": "signal_classification", ... },
      { "id": "knowledge_graph", ... },
      { "id": "impact_tree", ... }
    ],
    "consolidated_narrative": "## Technology–Industry Classification\n..."
  }
}
```

## Using as RAG for scenario generation (step 2)

For future development, pass the drivers JSON into your scenario LLM:

1. **Full context** — inject `rag_context.consolidated_narrative` as system/context prompt.
2. **Chunked retrieval** — index `rag_context.documents[]` in a vector store; retrieve by section.
3. **Structured features** — use `impact_tree.scenario_seeds` and `signal_classification.signals` as structured inputs alongside text.

Example prompt prefix:

```
You are generating future scenarios. Use ONLY the following technology drivers context:

{rag_context.consolidated_narrative}

Target year: {input.target_year}
Primary technology: {technology_industry_classification.primary_technology}
```

## Pipeline steps (internal)

1. LLM query classification (TOD + industries)
2. arXiv paper retrieval per technology
3. NLP entity/keyword extraction + embeddings
4. DVI signal classification (Wang & Zhu 2026)
5. Knowledge graph with ML edge probabilities
6. Impact tree with KG-ranked evolution paths

Steps 7–9 (scenarios, LLM explanations, recommendations) remain in the main `/api/analyze` endpoint.

## Dependencies

Reuses the shared `backend/` services (`LLMService`, `ArxivService`, `NLPService`, `DVIAnalyzer`, `KnowledgeGraphBuilder`, `ImpactTreeBuilder`). Requires the same `.env` configuration as the main backend.
