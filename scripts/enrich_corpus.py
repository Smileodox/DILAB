"""Corpus enrichment — inject dimension-targeted arXiv sources into the TREND pool.

Diversifies the driving-dimension buckets beyond the two regulatory mega-docs (WRC-23 Final Acts /
ITU Handbook) so market/geopolitical/technological drivers carry genuinely distinct content instead
of regulatory bleed. The MECHANISM is domain-agnostic (arxiv_ingest.run); the QUERY list below is
test-case config for the spectrum-monitoring domain, deliberately kept here (scripts/) and not
hardwired in src/. Idempotent (upsert by stable id) and traceable (source_id + year in metadata).

Run:  uv run python scripts/enrich_corpus.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.common import KBPool
from src.pipeline import arxiv_ingest

# (dimension, free-text query, arXiv categories, max_results). Curated for the spectrum test case.
QUERIES = [
    # market — economics / adoption / auctions / pricing (the most regulatory-diluted bucket)
    ("market", "spectrum auction valuation market competition pricing", ["econ.GN", "cs.GT"], 40),
    ("market", "dynamic spectrum access market adoption business model demand", ["cs.NI", "econ.GN"], 40),
    # geopolitical — sovereignty / international coordination / security / defense
    ("geopolitical", "spectrum policy national security sovereignty defense", ["cs.CY", "eess.SP"], 40),
    ("geopolitical", "cross-border interference international spectrum coordination", ["cs.CY", "cs.NI"], 30),
    # technological — external tech-push (already strong; top up distinct method areas)
    ("technological", "cognitive radio spectrum sensing deep learning", ["eess.SP", "cs.LG"], 30),
    ("technological", "6G spectrum sharing reinforcement learning autonomous", ["cs.NI", "cs.LG"], 30),
    # technological (expanded) — distinct external tech-push method areas
    ("technological", "spectrum sensing deep learning neural network signal detection", ["eess.SP", "cs.LG"], 40),
    ("technological", "reconfigurable intelligent surface RIS 6G wireless", ["eess.SP", "cs.IT"], 30),
    ("technological", "software defined radio FPGA signal processing architecture", ["eess.SP", "cs.AR"], 30),
    ("technological", "reinforcement learning dynamic spectrum access allocation", ["cs.LG", "cs.NI"], 40),
    ("technological", "large language model transformer wireless network optimization", ["cs.LG", "eess.SP"], 30),
    ("technological", "edge computing federated learning wireless spectrum", ["cs.NI", "cs.LG"], 30),
    ("technological", "millimeter wave massive MIMO beamforming 6G", ["eess.SP", "cs.IT"], 30),
    ("technological", "quantum sensing radio frequency signal detection", ["quant-ph", "eess.SP"], 20),
]


def main():
    total = 0
    per_dim: dict[str, int] = {}
    for i, (dim, query, cats, n) in enumerate(QUERIES):
        res = arxiv_ingest.run(
            query=query, categories=cats, max_results=n, pool=KBPool.TREND,
            output_path=f"data/outputs/arxiv_enrich_{dim}_{i}.json",
        )
        print(f"[{dim:13s}] +{res['n_chunks']:4d} chunks / {res['n_papers']} papers  q={query!r}", flush=True)
        per_dim[dim] = per_dim.get(dim, 0) + res["n_chunks"]
        total += res["n_chunks"]
        time.sleep(3)  # arXiv API politeness (~1 request / 3s)
    print(f"\nTotal added: {total} chunks  |  per dimension: {per_dim}")


if __name__ == "__main__":
    main()
