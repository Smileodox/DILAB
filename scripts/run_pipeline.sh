#!/bin/bash
set -e

TIMEOUT=3600
NBS=(
    "notebooks/02_bom_decomposition.ipynb"
    "notebooks/03_trend_scanning.ipynb"
    "notebooks/04_merge_drivers.ipynb"
    "notebooks/04b_manifestations.ipynb"
    "notebooks/05_cib_matrix.ipynb"
    "notebooks/05b_consistency.ipynb"
    "notebooks/06_scenario_generation.ipynb"
    "notebooks/07_analysis.ipynb"
)

for nb in "${NBS[@]}"; do
    echo ""
    echo "========================================"
    echo "START: $nb"
    echo "$(date)"
    echo "========================================"
    uv run jupyter nbconvert \
        --to notebook \
        --execute \
        --inplace \
        "$nb" \
        --ExecutePreprocessor.timeout=$TIMEOUT
    echo "DONE:  $nb  ($(date))"
done

echo ""
echo "========================================"
echo "ALL NOTEBOOKS COMPLETE"
echo "$(date)"
echo "========================================"
ls -la data/outputs/
