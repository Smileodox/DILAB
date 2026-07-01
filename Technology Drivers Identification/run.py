#!/usr/bin/env python3
"""
CLI: run Technology Drivers Identification and write RAG JSON to disk.

Usage:
  python run.py "Regulatory Spectrum Monitoring" --year 2035
  python run.py "Drone Warfare" --output output/drone_warfare.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_ROOT))

from src.pipeline import TechnologyDriversIdentificationPipeline  # noqa: E402


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug).strip("_")
    return slug[:60] or "drivers_output"


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Technology Drivers Identification — export RAG JSON artifact",
    )
    parser.add_argument("query", help="Foresight query or technology topic")
    parser.add_argument("--year", type=int, default=2035, help="Target year (default: 2035)")
    parser.add_argument(
        "--output", "-o",
        help="Output JSON path (default: output/<slug>_<year>.json)",
    )
    parser.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else (
        MODULE_ROOT / "output" / f"{slugify(args.query)}_{args.year}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Running Technology Drivers Identification…")
    print(f"  Query: {args.query}")
    print(f"  Target year: {args.year}")

    pipeline = TechnologyDriversIdentificationPipeline()
    result = await pipeline.run(query=args.query, target_year=args.year)

    payload = result.model_dump(mode="json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2 if args.pretty else None, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone. JSON written to:\n  {out_path}")
    print(f"\nSummary:")
    for key, val in result.processing_summary.items():
        print(f"  {key}: {val}")
    print(f"\nRAG documents: {len(result.rag_context.documents)} chunks")
    print(f"Consolidated narrative: {len(result.rag_context.consolidated_narrative)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
