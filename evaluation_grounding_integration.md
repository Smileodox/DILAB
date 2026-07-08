# Evidence-Grounded Evaluation — Integration Notes

**Date:** 2026-07-07 · **Branch:** `feature/combinatorial-landscape` · **Status:** implemented, tests green, not yet committed.

## What prompted this

Colleague **Whitenoizzz** pushed `origin/evaluation-pipeline`. On review it turned out to be an
**orphan branch** (single commit "evaluation changes", baselined on `main`, no common ancestor
with our branch) — so it could not be merged, only hand-ported. It did two independent things:

1. **Rewrote the scenario-evaluation stage** into a *pointwise, evidence-grounded LLM-auditor*:
   one scenario per call (no position bias), a per-scenario RAG evidence budget (own + driver +
   "stress" chunks, fixed caps against length bias), CIB promoting/inhibiting-relationship
   injection, **fact-extraction-before-scoring**, grounding-strength labels, and `[E#]`→chunk-id
   citation audit trails. But it **deleted** our MCDA/AHP+TOPSIS ranking, shipped **no tests**,
   and **hardwired** the R&S/spectrum/2035 domain.
2. Bundled a wholly separate **Flask "Technology Foresight" app** (BERTopic/spaCy/Plotly, impact
   trees, S-curve fitting) — overlaps the `AdiTest` branch.

## Decision

- **Augment, not replace.** The auditor and MCDA answer different questions (grounding quality
  *per* scenario vs. ranking *across* scenarios). We keep AHP+TOPSIS (and its 16 tests) and make
  the grounded scores the **inputs** to the ranker. The fact-extraction step is a direct attack on
  the LLM positivity-bias that the `structure.py` / contrastive-elicitation rigor already fights.
- **Flask "Technology Foresight" app → out of scope** (separate track; overlaps AdiTest).

## Changes (all on `feature/combinatorial-landscape`)

| File | Change |
|---|---|
| `src/config.py` | +7 tuning constants: evidence budget caps + CIB relevance/limits. |
| `src/models/evaluation.py` | `Assessment` gains `recommended_actions`, `grounding_strength`/`_reason`, `cib_consistency_strength`/`_reason` (all defaulted). Kept numeric MCDA fields + `AHPWeights`/`MCDAResult`. Resolved the `actionability` str↔float clash (numeric stays; prose → `recommended_actions`). |
| `src/prompts/evaluation.py` | Added `SCENARIO_POINTWISE_EVIDENCE_ASSESS` + `SCENARIO_POINTWISE_SYSTEM`, **neutralized** to `DomainProfile.prompt_kwargs()` slots, extended to emit numeric `actionability_score`/`time_horizon_score`/`severity_score` so MCDA gets all 5 criteria. Kept legacy `SCENARIO_ASSESS`. |
| `src/pipeline/evaluation.py` | Ported `build_scenario_evidence` (rag-adapted via `src.rag.retrieve`), `build_cib_context_by_scenario`, `load_cib_state`, helpers, `assess_single_scenario_pointwise`, pure `_assessment_from_judge`, orchestrator `assess_scenarios_pointwise`. Kept MCDA + comparative functions + the `0.4·driver+0.6·cib` confidence blend. Rewrote `run()` to feed grounded assessments into `run_mcda` and emit `mcda.rankings` **and** `evaluation_metadata`. Backward-compatible signature + optional `cib_state_path`. |
| `run_combinatorial.py`, `run_morphological.py` | Pass `cib_state_path` so CIB context is populated. |
| `tests/test_evaluation_grounding.py` | New, offline (no live LLM): grounded→MCDA flow, evidence-budget caps, `[E#]`→chunk-id mapping, CIB selection/threshold/cap/sentinel, `_assessment_from_judge` types, confidence-blend guard. |
| `tests/test_domain.py` | Registered the new prompt call-kwargs in the domain-neutrality allowlist. |

## Verification

- `uv run pytest -q` → **158 passed** (warnings are pre-existing sklearn `ConvergenceWarning`s in `test_structure.py`).
- Offline end-to-end (mocked LLM+RAG): one call per scenario, grounded scores populate all 5 MCDA
  criteria + grounding fields, `domain_context` reflects the docked profile (not hardwired), MCDA
  ranks with valid TOPSIS closeness.

## Deferred / out of scope

- Live end-to-end run (needs Azure creds + docked Chroma KB).
- Notebook `07_analysis.ipynb` grounding cross-tab cells.
- Flask "Technology Foresight" app — evaluate on the AdiTest track.
- Possible future unification: gate MCDA / representative selection on the `structure.py` null-model verdict.
