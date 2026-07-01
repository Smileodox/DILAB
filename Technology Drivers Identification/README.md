# Technology Drivers Identification

**Self-contained, zip-ready package** for pipeline step 1: identify technology drivers from a foresight query and export a **RAG JSON artifact** for downstream scenario LLMs.

No dependency on the parent `backend/` folder — everything needed is inside this directory.

## Folder structure

```
Technology Drivers Identification/
├── tdi/
│   ├── config.py
│   ├── pipeline.py
│   ├── rag_builder.py
│   ├── serializers.py
│   ├── models/
│   │   ├── schemas.py            # All domain Pydantic models
│   │   └── output.py             # RAG export schema
│   └── services/
├── run.py                        # CLI
├── api.py                        # Standalone FastAPI server
├── requirements.txt
├── .env.example
├── schema/
│   ├── technology_drivers_output.schema.json
│   └── example_output.json
└── output/                       # Generated JSON files
```

## Setup (fresh machine / after unzip)

```bash
cd "Technology Drivers Identification"

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set OPENROUTER_API_KEY
```

Requires **Python 3.11+** and an [OpenRouter](https://openrouter.ai) API key.

## Run — CLI

```bash
python run.py "Regulatory Spectrum Monitoring" --year 2035
python run.py "Drone Warfare" -o output/drone_warfare_2035.json
```

Writes JSON to `output/<slug>_<year>.json`.

## Run — API server

```bash
uvicorn api:app --reload --port 8002
```

```http
POST http://localhost:8002/identify
Content-Type: application/json

{
  "query": "Drone Warfare",
  "target_year": 2035
}
```

## JSON output sections

| Section | Description |
|---------|-------------|
| `technology_industry_classification` | LLM TOD taxonomy + industries |
| `research_evidence` | arXiv papers, entities, keywords |
| `signal_classification` | DVI scores per technology |
| `knowledge_graph` | Nodes, edges, propagation paths |
| `impact_tree` | Evolution paths + scenario seeds |
| `rag_context` | Pre-chunked text for LLM RAG |

See `schema/technology_drivers_output.schema.json` for the full JSON Schema.

## Using as RAG for scenario generation (step 2)

```python
import json

with open("output/drone_warfare_2035.json") as f:
    drivers = json.load(f)

context = drivers["rag_context"]["consolidated_narrative"]
primary = drivers["technology_industry_classification"]["primary_technology"]
seeds = drivers["impact_tree"]["scenario_seeds"]

# Pass `context` + `seeds` to your scenario LLM prompt
```

## Models included

All Pydantic models live in `tdi/models/`:

- **`schemas.py`** — `ClassificationResult`, `TechnologySignal`, `KnowledgeGraph`, `ImpactTreeNode`, `QueryRequest`, etc.
- **`output.py`** — `TechnologyDriversIdentificationOutput` (the zip export schema)

## Sharing as ZIP

1. Zip this entire folder (exclude `venv/` and `output/*.json` if large).
2. Recipient follows **Setup** above.
3. Run `python run.py "your query"`.

The package is fully standalone.
