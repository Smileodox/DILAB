#!/bin/bash
# The "best / most-truthful" mode run, per the project's own findings:
#   contrastive CIB elicitation (de-biased cross-impacts, breaks the positivity bias)
#   + the combinatorial method (broad soft-CIB sampling + clustering -> continuum-native
#     scenarios, instead of imposed fixed-point boxes) + grounded evaluation.
# Reuses the current morphbox_state.json (14 drivers, 56 manifestations). Regenerates
# cib_state.json in contrastive mode, then runs the combinatorial path end-to-end.
#   bash scripts/run_best.sh 2>&1 | tee data/outputs/_e2e_best.log
set -euo pipefail

echo "############ STEP 1/2 — CIB (CONTRASTIVE elicitation) ############"
uv run python -c "
from src.pipeline import cib
from src.rag import get_collection
import json
drivers = json.load(open('data/outputs/morphbox_state.json'))['drivers']
print(f'Contrastive CIB Delphi panel for {len(drivers)} drivers', flush=True)
cib.run(collection=get_collection(), panel_mode=True, driver_ids=drivers, cib_mode='contrastive')
"

echo "############ STEP 2/2 — Combinatorial path (soft-CIB + clustering + grounded eval) ############"
uv run python run_combinatorial.py

echo "############ BEST-MODE RUN COMPLETE ############"
ls -la data/outputs/*combi*.json data/outputs/cib_state.json