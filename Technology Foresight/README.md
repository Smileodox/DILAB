# Technology Foresight

Flask web app for corpus-driven technology foresight: BERTopic clustering, lifecycle evolution, LLM causal reasoning, and 2×2 scenario planning.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Add your API keys to `.env`:

```
OPENROUTER_API_KEY=sk-or-...
# Optional — higher Semantic Scholar rate limits (free key):
# SEMANTIC_SCHOLAR_API_KEY=...
# Optional — comma-separated if the default free models fail:
# OPENROUTER_MODEL=deepseek/deepseek-v4-flash:free,qwen/qwen3-next-80b-a3b-instruct:free
```

Paper search uses the [Semantic Scholar API](https://www.semanticscholar.org/product/api). No key is required, but a free API key avoids rate limits.

The original `deepseek/deepseek-v3-base:free` model is no longer on OpenRouter; the app tries several free models automatically.

### Hugging Face cache

Embedding models are stored under `.cache/huggingface/` inside the project (not `~/.cache`), which avoids macOS permission errors in restricted environments. The first run downloads ~80MB for `all-MiniLM-L6-v2`.

## Run

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Usage

1. **Upload** — Drop PDF papers and/or patent JSON files.
2. **Semantic Scholar** — Enter a search query, set count (1–100), click **Fetch preview** to confirm titles.
3. **Run Analysis** — Pipeline runs synchronously; progress bar polls `/api/progress/<job_id>`.
4. **Dashboard** — Four tabs: Topic Clusters, Evolution, Causal Reasoning, Scenarios.

Results are saved under `uploads/<job_id>/result.json`.

## Stack

- Python, Flask, Jinja2, vanilla JS
- sentence-transformers (`all-MiniLM-L6-v2`), BERTopic (UMAP + HDBSCAN)
- spaCy SAO extraction, OpenRouter (`deepseek/deepseek-v3-base:free`)
- Plotly.js charts, D3.js impact trees
