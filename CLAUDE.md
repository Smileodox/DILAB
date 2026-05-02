# DILAB - LLM-Augmented Strategic Technology Foresight

## Project
Python tool for LLM-augmented scenario planning using Morphological Analysis + Cross-Impact Balance (CIB). Built for Rohde & Schwarz DILAB partnership.

## Tech Stack
- Python 3.11+, managed with `uv`
- LLM: Azure AI Foundry (GPT-4o) via openai SDK
- RAG: LlamaIndex + Chroma (dev) / Qdrant (prod)
- Knowledge Graph: NetworkX (prototype) / Neo4j (prod)
- Document parsing: Unstructured.io / Docling
- Evaluation: RAGAS, SALib
- Testing: pytest

## Conventions
- Code and docs in English, communication in German
- Type hints on all public functions
- Pydantic models for all structured data (drivers, scenarios, cross-impact matrices)
- Structured LLM output only (no freeform generation without schema)

## Project Structure
```
src/foresight/
  kb/          # Knowledge base: ingestion, RAG, knowledge graph
  cib/         # Cross-Impact Balance algorithm
  drivers/     # Technology driver extraction and modeling
  scenarios/   # Scenario generation and narrative
  eval/        # Evaluation: faithfulness, consistency, quality metrics
  analysis/    # Quantitative analysis: Monte Carlo, sensitivity, clustering
```

## Key Commands
```bash
uv run pytest                    # Run tests
uv run python -m foresight.cib   # Run CIB standalone
```
