#!/bin/bash
# Full end-to-end run of the whole foresight pipeline, ending with the NEW integrations
# (love's evidence-grounded evaluation + Adi-inspired temporal/DVI axes) so their outputs
# are freshly produced. Long-running (CIB Delphi panel + scenario generation) — run detached.
#
#   bash scripts/run_full.sh 2>&1 | tee data/outputs/_e2e_full.log
set -euo pipefail

stage () { echo; echo "############################################################"; echo "# $1"; echo "# $(date)"; echo "############################################################"; }

# 1. Canonical notebook pipeline: BOM -> trends -> merge -> manifestations -> CIB ->
#    consistency -> scenarios -> analysis (KB already ingested; starts at NB02).
stage "STAGE 1/4 — Notebook pipeline (NB02 -> NB07)"
bash scripts/run_pipeline.sh

# 2. Grounded evaluation on the baseline scenarios: love's evidence-grounded pointwise auditor
#    (fact-extraction before scoring) feeds AHP+TOPSIS. Overwrites NB07's legacy comparative
#    final_analysis.json with the grounded version (+ evaluation_metadata / evidence audit).
stage "STAGE 2/4 — Grounded evaluation (baseline scenarios)"
uv run python -c "from src.pipeline import evaluation; evaluation.run(cib_state_path='data/outputs/cib_state.json')"

# 3. Combinatorial-landscape path (this branch's flagship): soft-CIB sampling + clustering +
#    grounded evaluation on the representatives (final_analysis_combi.json).
stage "STAGE 3/4 — Combinatorial path (grounded eval on representatives)"
uv run python run_combinatorial.py

# 4. Temporal / DVI signal-maturity: per-driver emergence + visibility_trend + diffusion +
#    weak-signal, over the freshly rebuilt drivers/KB (temporal_state.json).
stage "STAGE 4/4 — Temporal / DVI enrichment"
uv run python -c "from src.pipeline import temporal; temporal.run()"

stage "FULL RUN COMPLETE"
ls -la data/outputs/*.json