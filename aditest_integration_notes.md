# AdiTest — Evaluation & Harvest Notes

**Date:** 2026-07-07 · **Branch:** `feature/combinatorial-landscape` · **Status:** two pieces implemented, tests green, not yet committed.

## What AdiTest actually is

`origin/AdiTest` (Aditya Purwar) is a **clean feature branch off `main`**, purely additive —
it modifies **nothing** in `src/`. It drops in **two standalone apps**:

1. **`Technology Foresight/`** — BERTopic + MiniLM **Flask** app. **Byte-identical** to the app
   already bundled on `origin/evaluation-pipeline` (same source + same `uploads/` artifacts,
   plus one stray `.pyc`). Not new. → **separate track** (see the evaluation-pipeline notes).
2. **`Technology Drivers Identification/`** — a **FastAPI `tdi/` package**, Adi's genuinely-new
   work, unique to AdiTest. LLM taxonomy classification (Lee et al. 2022) from arXiv, a DVI/Yoon
   weak-signal scorer (Wang & Zhu 2026 MLWS-TF / Yoon 2012), a knowledge graph + cascade, and a
   RAG-JSON export. **Well-organized but:** hardwired to spectrum/telecom in four layers
   (arXiv `cat:` filter, NLP dictionaries, LLM hints/fallbacks, default strings), ~⅓ dead code
   (`orchestrator`, `scenario_generator`, `graph_propagation` never called on the export path),
   its "ML" layer is mostly hand-set weights, and its DVI code is degenerate on a thin corpus
   (emits `strong_signal` off a single paper, no honesty guard). Traceability is paper-level and
   name-only — below our `source_chunk_ids` bar.

## What we harvested (concept, not code — everything re-anchored on our KB + honesty contract)

### 1. arXiv ingester → `src/pipeline/arxiv_ingest.py`  *(highest value)*
A domain-agnostic source expander. Stdlib `urllib` fetch (**no new dependency**), a **pure**
`parse_arxiv_atom` Atom parser, and `ingest_papers` mapping each paper into the SAME
`Source`/`Chunk` shape + Chroma metadata (`source_id` + `year`) that `kb.ingest` writes — so
drivers stay traceable and `temporal.py` gets dated, spread-out literature. The category filter
is an **optional parameter** (never hardwired); default is an unrestricted, domain-neutral query.
Reuses `kb.chunk_text`/`_open_collection`/`embed`. `clear=False` (augments, doesn't replace).

### 2. DVI-lineage axes → `src/pipeline/temporal.py`  *(enriches a module we already own)*
Added two honest axes to `temporal_stats`, alongside the existing `recency_shift` (LEVEL):
- **`visibility_trend`** (SLOPE) — rising / flat / waning from a robust recent-vs-older evidence
  split at the corpus median (the DoV/growth *intent* — no curve fit, no normalization).
- **`diffusion`** (BREADTH) — broad / moderate / narrow from the count of **distinct sources**
  grounding a driver (the DoD *intent*, via our explicit driver→source graph, not term matching).
Sharpened `is_weak_signal` to the classic combination: emerging **AND** thin **AND** not broadly
sourced. Temporal axes stay gated by the existing `insufficient temporal evidence` verdict;
breadth (not a temporal claim) is reported whenever source data is present. `run()` now also
pulls `source_id` from chunk metadata to build the breadth signal.

### Tests
`tests/test_temporal.py` (11) — honesty gate, level/slope/breadth, refined weak-signal, backward
compat. `tests/test_arxiv_ingest.py` (5) — query builder, pure Atom parser, KB-mapping
traceability (`source_id`+`year`) + short-abstract skip. Full suite: **174 passed**.

## Deliberately skipped (redundant or conflicting)

- **`Technology Foresight/` BERTopic Flask app** — duplicate of evaluation-pipeline; separate track.
- **TDI second scenario/impact-tree engine** (`orchestrator`, `scenario_generator`) — dead code,
  inferior to our `scenario_gen` + CIB/MCDA.
- **`graph_propagation`** — dead, unsigned single-hub cascade; our signed CIB matrix supersedes it.
- **OpenRouter LLM infra** — we are Azure-OpenAI-centric.
- **All hardwired-domain assets** — NLP dictionaries, `cat:` filter constants, `REFERENCE_CATEGORIES`,
  `INDUSTRY_TECH_HINTS`, `_infer_*`, spectrum fallbacks — violate the domain-agnostic deliverable.
- **`ml_probability` GMM probabilities** — not statistically sound at N≈16; uncalibrated.
- **DVI module as-is** — degenerate on thin corpora, no honesty guard (harvested the concept only).
- **Committed `.pyc` / `uploads/` run artifacts** — noise.

## Deferred / possible follow-ups

- Live arXiv fetch + KB augmentation end-to-end (needs network + Azure embeddings).
- Wire `arxiv_ingest.run(...)` into a pipeline stage / derive its query+categories from `DomainProfile`.
- Lee-taxonomy-guided LLM driver classification to fill the still-stubbed `bom.py` — high effort,
  needs a full neutralization rewrite; not done.
- RAG-export interchange schema (evaluated, low urgency — not implemented).
