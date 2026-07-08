# Scenario-Differentiation Fix — Implementation Plan (resume after /clear)

**Date:** 2026-07-07 · **Branch:** `feature/combinatorial-landscape` · **Deadline:** presentation **Mon 2026-07-13** (mixed academic + R&S/sponsor panel). Nothing committed yet.

## FOR THE NEXT SESSION — READ THIS FIRST
You are resuming with no memory of the prior conversation. This file + the memory index are your source of truth.

**Environment is ready (verified 2026-07-07):** Azure creds set (4-endpoint round-robin pool); `knowledge_base` Chroma collection = **2875 chunks** (already arXiv-augmented); `uv run python run_full.py --dry-run` imports clean; a full run took **~12.6 min** (CIB Delphi is the long pole) → **always launch runs with `run_in_background: true` + log to a file**; monitor the log. Models: CIB/eval/scenario = `gpt-5.4` (pooled across all 4 endpoints — this avoids the gpt-4.1-mini single-endpoint 429 storm).

**Line numbers below are approximate — RE-READ each file before editing.** Files to read first: `src/pipeline/trends.py`, `src/pipeline/merge.py`, `src/pipeline/cib.py`, and `src/models/drivers.py` (DimensionType enum values must match the DRIVING_DIMENSIONS keys: `regulatory`/`market`/`geopolitical`).

**Execution order:**
1. Part 1 (`trends.py` block) → `uv run pytest tests/test_domain.py -q` (neutrality guard).
2. Part 2 (`merge.py` guard) → `uv run pytest -q` (nothing regresses).
3. Part 3 (`cib.py` dissent aggregation) → `uv run pytest tests/test_cib_mode.py -q`.
4. **Activate the CIB de-bias for the re-run** — cleanest is a config flag: add `CIB_DISSENT_PRESERVING = os.environ.get("CIB_DISSENT_PRESERVING","")` in `src/config.py`, default it ON in `cib.run`, so `run_full` picks it up WITHOUT editing call sites. (Otherwise you MUST edit `run_full.py`'s `cib.run(...)` call to pass `dissent_preserving=True` — easy to forget.)
5. Re-run: `uv run python run_full.py --skip-arxiv` **in background**, log to `data/outputs/_e2e_fix.log`.
6. Measure vs baseline (below) and report the lift honestly.

**Invocation:** the user will say something like "implement differentiation_fix_plan.md". If they just say "continue the fix", the memory `project_differentiation_fix` points here.

## Problem
The foresight pipeline runs end-to-end but scenarios come out **flat / undifferentiated**: MCDA criteria barely spread (impact 6–9 but probability/actionability/risk spread ≤1), grounding_strength + cib_consistency = "moderate" for ALL scenarios, combinatorial null-model verdict = **"above null, but no usable clusters"** (silhouette ~0.076, floor is 0.25). We ran BOTH CIB modes (absolute 89% pos / contrastive 70% pos) and BOTH scenario methods (fixed-point + combinatorial) — all flat.

## Verified root cause (diagnostic workflow `wf_e00ecba1-402`, adversarially checked)
1. **PRIMARY — driver-layer collapse.** Morphological field = **1 driving axis + 13 co-varying response axes** → 1-D continuum by construction. `merge_state` axis_role = 18 response / 1 driving (dimension_type: hardware 16, software 2, regulatory 1; **zero market, zero geopolitical**). Traced exactly: `trends.py` produces a **monoculture** (12 regulatory paraphrases over the orphan chunks); `merge.py` `consolidate()` then **collapses all 12 into ONE** "Regulatory Frameworks" blob (absorbing even the lone geopolitical axis). That lone driving axis is also the **weakest CIB node** (influence 3 vs FFT 16), so it's nominal, not a real fork. `select_top_drivers` is NOT the leak (it ranked the driving driver #1).
2. **CO-PRIMARY — CIB positivity bias.** 89% positive (absolute) / 70% (contrastive), **0 strong-negative cross-impacts**; median/Delphi aggregation washes out trade-offs personas actually articulated (237 contrastive reasonings had inhibition ≥2). Makes the 13 response axes couple into one "more-capability" super-dimension.
3. **CONTRIBUTING — KB thin/lopsided.** 50% of chunks are two descriptive mega-docs (WRC-23 Final Acts + ITU Handbook); forward-looking policy only ~10.5%; 18/19 drivers harvested from the 7.4% product pool. (Enrichment is roadmap, not the bottleneck.)
4. **NOT a cause — the machinery.** Proven sound: synthetic coupling ON → silhouette ~0.72; agriculture domain **equally flat** (silhouette ~0.149) → the deficit generalizes, which *validates* the domain-agnostic engine.

## The fix (3 parts)

### Part 1 — `src/pipeline/trends.py`: dimension-bucketed extraction  **[PRIMARY lever]**
- **DONE already:** added `DimensionType` to the drivers import; added `DRIVING_DIMENSIONS` constant (generic anchors for `regulatory` / `market` / `geopolitical`).
- **TODO:** replace the clustering + extraction block in `run()` (the old `# --- 4. KMeans cluster ---` through `print(f"  Extracted {len(extracted)} candidate drivers")`). New logic:
  1. `anchor_embs = embed(list(DRIVING_DIMENSIONS.values()))`; `dim_assign = _cosine_sim(orphan_embs, anchor_embs).argmax(axis=1)` → bucket each orphan chunk to its nearest driving dimension.
  2. For each non-empty dimension bucket: `k_dim = max(1, min(round(n_clusters * bucket_size/n_orphan), bucket_size//min_cluster_size or 1))`; if tiny, k_dim=1 (single driver from top chunks nearest the bucket mean). Else KMeans(k_dim) within the bucket.
  3. Per sub-cluster: top-K chunks nearest centroid → `CLUSTER_DRIVER_EXTRACT.format(chunks_text=..., **pkw)`; build `TechDriver(..., dimension_type=DimensionType(dim_name), ...)` — **stamping the dimension so distinct axes survive merge.** System prompt: "identifying {dim_name} environmental drivers for ... {pkw['domain']}".
  4. Keep the BOM-overlap post-filter unchanged. Update `metadata` (drop stale `k`; record per-dimension counts / total sub-clusters).
- Guarantees ≥1 driver per non-empty driving dimension → independent driving-axis count 1 → ~3–4.

### Part 2 — `src/pipeline/merge.py`: cross-dimension merge guard  **[protect the axes]**
- In `consolidate()`, add `_same_dim(a, b)` = `True` if same `dimension_type` OR either is `UNCLASSIFIED`.
- **Stage 2 (cosine, line ~199):** only merge `j` into `i` if `sim > SIMILARITY_THRESHOLD AND _same_dim(...)`.
- **Stage 3 (LLM grouping, ~line 248):** after `groups`, for each group keep only members whose `dimension_type` matches the rep's (or UNCLASSIFIED); drop cross-dimension members. (The existing cross-type guard in `llm_match` L101-106 is the template.)
- Effect: regulatory/market/geopolitical (and hardware/software response) axes are no longer collapsed into one blob.

### Part 3 — `src/pipeline/cib.py`: dissent-preserving aggregation  **[co-primary backstop, no new LLM cost]**
- Read `_aggregate_panel` (~line 116) + how `run()` builds the matrix from `persona_scores_map`.
- Add a **dissent-preserving** aggregation: when any persona votes an inhibiting/net score ≤ −2, keep the negative sign (carry promoting/inhibiting separately) instead of median-washing to ~0/positive. Add param `dissent_preserving: bool = False` (default off → keeps `tests/test_cib_mode.py` green); enable it for the re-run via `cib.run(dissent_preserving=True)` (thread through `run_full`/`run_subset` CIB call, or a config flag `CIB_DISSENT_PRESERVING`).
- Check `tests/test_cib_mode.py` (5 tests) still pass with default off.

## Re-run + measure
- Command: `uv run python run_full.py --skip-arxiv` (KB already arXiv-augmented; re-runs trends→merge→manifestations→CIB→scenarios→landscape→grounded-eval→temporal→strategic-framing on pooled **gpt-5.4**). `run_combinatorial.py` already fixed to default narratives to `SCENARIO_MODEL` (gpt-5.4) — no more gpt-4.1-mini single-endpoint 429 storm.
- **Measure vs baseline** (baseline: driving=1, silhouette 0.076, MCDA impact spread 3 / others ≤1, grounding all "moderate"):
  - driving-axis count + dimension_type spread in `merge_state.json`;
  - silhouette + PC1 share (`landscape_state*.json` `structure`);
  - MCDA criteria spreads + grounding_strength distribution (`final_analysis*.json`).
- **Expected (honest):** driving axes 1 → ~3–4; PC1 share falls from ~0.07; silhouette rises toward (NOT guaranteed past) 0.25; MCDA spreads widen. A defensible lift, **not** a promise of clean clusters.

## Verification
- `uv run pytest -q` must stay green — especially `test_domain.py` (domain-neutrality guard: DRIVING_DIMENSIONS anchors are generic, no banned terms), `test_mcda.py`, `test_cib_mode.py`, `test_evaluation_grounding.py`, `test_temporal.py`, `test_arxiv_ingest.py`.
- Confirm `run_full.py --dry-run` still imports clean.

## Presentation framing (ready regardless of the re-run's lift)
1. **Lead with credibility:** the engine works correctly — proven sound (synthetic 0.72; agriculture 0.149) — it *faithfully measures* a real input property and refuses to hallucinate clusters. That integrity is the selling point.
2. **Quantified, localized root cause:** 1 driving axis (the weakest CIB node), traced to trend-monoculture + merge-collapse — pinpointed, not hand-waved.
3. **It generalizes → validates domain-agnosticism:** agriculture equally flat; the deficit is a method/elicitation property, not a spectrum quirk.
4. **Honest about the corpus:** thin/lopsided (2 mega-docs = 50% of chunks; policy layer 10.5%); enrichment with *opposed* driving sources is roadmap.
5. **Close with the fix + calibrated expectations:** bounded 2-file change lifts driving axes 1→~4 + free CIB de-biasing backstop; measure live; under-promise (axis count up, not guaranteed clusters).

**Honest caveats:** "primary" is really co-primary with CIB positivity bias; fix is necessary-but-maybe-not-sufficient; do NOT present the (false) "extraction bypassed the driving layer" claim — it's collapse/dilution at merge, not bypass; silhouette varies run-to-run (cite ranges, all < 0.25); MCDA compression is partly LLM eval-compression (may need score-anchoring later).

## Current state snapshot (for resume)
- **Edits already made:** `trends.py` (DimensionType import + DRIVING_DIMENSIONS constant) — the rest of Part 1 + Parts 2/3 are TODO.
- **Runs completed:** `run_full.py` baseline (absolute + fixed-point) OK; best-mode (contrastive + combinatorial, pooled gpt-5.4) OK — both flat (~0.07). Absolute CIB backed up to `data/outputs/cib_state_absolute.json`; current `cib_state.json` is contrastive.
- **New files this effort (uncommitted):** `run_full.py`, `scripts/run_full.sh`, `scripts/run_best.sh`, `src/pipeline/arxiv_ingest.py`, `tests/{test_temporal,test_arxiv_ingest,test_evaluation_grounding}.py`, `evaluation_grounding_integration.md`, `aditest_integration_notes.md`, this file.
- **Deferred:** frontend surfacing of grounded-eval + temporal (task; see web-app map in prior notes) — do AFTER the differentiation fix + re-run.
