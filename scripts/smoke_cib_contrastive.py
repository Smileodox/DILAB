"""Cheap A/B smoke test: does contrastive CIB break the LLM positivity bias?

Runs the REAL cib.run() over the 14 selected drivers under identical minimal conditions
(single persona, no RAG, no Delphi) for both prompt modes and reports negative-share.
Bar to clear: negative-share moves from ~0% (documented baseline) toward the CCA-equivalent
(~30%). Writes to cib_smoke_*.json (does NOT clobber cib_state.json). Throwaway diagnostic.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.pipeline import cib
from src.pipeline.domain import load_profile

profile = load_profile()
morph = json.load(open("data/outputs/morphbox_state.json"))
driver_ids = morph["drivers"]
print(f"Smoke: {len(driver_ids)} drivers, single persona, no RAG, both modes\n", flush=True)


def stats(state):
    m = state["matrix"]
    n = len(m)
    flat = [m[i][j] for i in range(n) for j in range(n) if i != j]
    neg = sum(1 for s in flat if s < 0)
    zero = sum(1 for s in flat if s == 0)
    pos = sum(1 for s in flat if s > 0)
    return neg, zero, pos, len(flat), sum(flat) / len(flat)


summary = {}
for mode in ("absolute", "contrastive"):
    print(f"=== CIB mode: {mode} ===", flush=True)
    state = cib.run(
        collection=None,
        panel_mode=False,
        driver_ids=driver_ids,
        cib_mode=mode,
        delphi_rounds=1,
        output_path=f"data/outputs/cib_smoke_{mode}.json",
        model="gpt-5.4",   # pooled across 4 endpoints → no rate-limit contamination
        max_workers=8,
    )
    neg, zero, pos, tot, mean = stats(state)
    summary[mode] = (neg, zero, pos, tot, mean)
    print(f"  RESULT {mode}: neg {neg}/{tot} ({neg/tot*100:.1f}%), "
          f"zero {zero} ({zero/tot*100:.1f}%), pos {pos} ({pos/tot*100:.1f}%), "
          f"mean {mean:+.3f}\n", flush=True)

print("=== A/B SUMMARY ===", flush=True)
for mode, (neg, zero, pos, tot, mean) in summary.items():
    print(f"  {mode:12s}: {neg/tot*100:5.1f}% negative | mean net {mean:+.3f}", flush=True)
