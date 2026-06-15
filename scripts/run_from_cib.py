"""Run CIB + remaining pipeline (NB05b, NB06, NB07) after NB02-NB04b are done."""
from __future__ import annotations
import subprocess
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.rag import get_collection
from src.pipeline import cib

print("=" * 60)
print("STEP 1: CIB Matrix (parallel, max_workers=5)")
print("=" * 60)
collection = get_collection()
t0 = time.time()
state = cib.run(collection=collection, max_workers=5)
elapsed = time.time() - t0
n = len(state["driver_ids"])
print(f"\nCIB done: {n}×{n} matrix, {n*(n-1)} pairs in {elapsed:.0f}s")

NOTEBOOKS = [
    "notebooks/05b_consistency.ipynb",
    "notebooks/06_scenario_generation.ipynb",
    "notebooks/07_analysis.ipynb",
]

for nb in NOTEBOOKS:
    print(f"\n{'=' * 60}")
    print(f"START: {nb}  ({time.strftime('%H:%M:%S')})")
    print("=" * 60)
    result = subprocess.run(
        [
            "uv", "run", "jupyter", "nbconvert",
            "--to", "notebook", "--execute", "--inplace",
            nb,
            "--ExecutePreprocessor.timeout=1200",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR in {nb}:")
        print(result.stderr[-2000:])
        sys.exit(1)
    print(f"DONE:  {nb}  ({time.strftime('%H:%M:%S')})")

print("\n" + "=" * 60)
print("ALL DONE")
print("=" * 60)
import json
for fname in ["cib_state.json", "consistency_state.json", "scenario_state.json", "final_analysis.json"]:
    path = f"data/outputs/{fname}"
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  {fname:35s} {size//1024:5d} KB")
    else:
        print(f"  {fname:35s} MISSING")
