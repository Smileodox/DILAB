"""Derive the DomainProfile from the docked knowledge base.

Run this FIRST when you dock a new KB — every downstream step reads the profile and needs
no code/prompt changes for a new domain.

  uv run python run_domain.py
  DOMAIN_HORIZON=2040 DOMAIN_ACTOR="Acme Corp" uv run python run_domain.py   # pin overrides
"""
from __future__ import annotations

import argparse
import logging

from src.pipeline import domain


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Derive DomainProfile from the docked KB")
    ap.add_argument("--model", default=None, help="profiling model (default: config.DOMAIN_MODEL)")
    ap.add_argument("--n-sample", type=int, default=50, help="KB chunks to sample for inference")
    args = ap.parse_args()
    domain.run(model=args.model, n_sample=args.n_sample)


if __name__ == "__main__":
    main()
