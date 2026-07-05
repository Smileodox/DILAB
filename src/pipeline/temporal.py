"""Temporal / lifecycle enrichment for technology drivers — the one capability harvested
from the BERTopic-style approach, built on OUR (chunk-grounded) drivers instead of topics.

Each driver already links to its source chunks (``TechDriver.source_chunk_ids``); each chunk
carries the publication ``year`` of its source. This stage rolls those years up into an
HONEST, coarse temporal signal per driver — is it grounded in recent or older literature,
*relative to the corpus baseline* — plus a weak-signal flag.

Deliberately NOT logistic S-curve lifecycle fitting: a small curated KB is temporally too
thin for that, and manufacturing a lifecycle stage we can't support is exactly the kind of
over-reading ``structure.py`` exists to prevent. So the signal is:
  - relative to the CORPUS baseline (a driver is "emerging" only if its median year is
    younger than the corpus as a whole — recency alone means nothing if the whole corpus is
    recent), and
  - guarded by an ``insufficient temporal evidence`` verdict when the corpus has too few /
    too-undated / single-year sources (mirrors ``structure.py``'s ``has_usable_clusters``).

The core (``temporal_stats``) is pure and numpy-free → fully unit-testable offline. ``run``
only adds the I/O (read merge_state + chunk years, write temporal_state.json).
"""
from __future__ import annotations

import json
import os
import statistics


def _parse_year(value) -> int | None:
    """Coerce a metadata year (stored as a string) to a plausible int, else None."""
    try:
        y = int(str(value).strip()[:4])
    except (ValueError, TypeError):
        return None
    return y if 1900 <= y <= 2100 else None


def temporal_stats(
    driver_years: dict[str, list[int]],
    corpus_years: list[int],
    min_corpus_dated: int = 4,
    min_driver_dated: int = 2,
    shift_threshold: float = 1.5,
    weak_signal_max_dated: int = 3,
) -> dict:
    """Per-driver temporal profile relative to the corpus baseline. Pure (no I/O).

    ``recency_shift`` = driver median year − corpus median year (positive ⇒ grounded in
    younger-than-typical literature). Emergence is classified off that RELATIVE shift, never
    off absolute recency. Returns per-driver records + a corpus summary + an honesty verdict.
    """
    corpus = [y for y in (int(v) for v in corpus_years)]
    n_corpus = len(corpus)
    distinct = len(set(corpus))
    span = (max(corpus) - min(corpus)) if corpus else 0
    c_med = statistics.median(corpus) if corpus else None

    corpus_summary = {
        "n_dated": n_corpus,
        "year_min": min(corpus) if corpus else None,
        "year_max": max(corpus) if corpus else None,
        "year_median": c_med,
        "year_span": span,
        "distinct_years": distinct,
    }

    # Honesty guard: too little temporal spread to say anything (analogous to
    # structure.py's "≈ uniform random" → has_usable_clusters=False).
    has_signal = n_corpus >= min_corpus_dated and distinct >= 2 and span >= 2

    drivers = []
    for did, years in driver_years.items():
        ys = [int(v) for v in years]
        n = len(ys)
        rec = {
            "driver_id": did,
            "n_dated": n,
            "year_min": min(ys) if ys else None,
            "year_median": statistics.median(ys) if ys else None,
            "year_max": max(ys) if ys else None,
            "recency_shift": None,
            "emergence": "unknown",     # emerging | established | steady | unknown
            "is_weak_signal": False,
            "confidence": "low",
        }
        if has_signal and n >= min_driver_dated and c_med is not None:
            shift = statistics.median(ys) - c_med
            rec["recency_shift"] = round(shift, 2)
            if shift >= shift_threshold:
                rec["emergence"] = "emerging"          # younger-than-typical literature
            elif shift <= -shift_threshold:
                rec["emergence"] = "established"        # grounded in older-than-typical work
            else:
                rec["emergence"] = "steady"
            rec["confidence"] = "medium" if n >= min_corpus_dated else "low"
            # A weak signal: recent-skewed AND thinly grounded — an early indicator, low confidence.
            rec["is_weak_signal"] = rec["emergence"] == "emerging" and n <= weak_signal_max_dated
        drivers.append(rec)

    return {
        "corpus": corpus_summary,
        "drivers": drivers,
        "has_temporal_signal": bool(has_signal),
        "verdict": "usable temporal signal" if has_signal else "insufficient temporal evidence",
        "params": {
            "min_corpus_dated": min_corpus_dated,
            "min_driver_dated": min_driver_dated,
            "shift_threshold": shift_threshold,
            "weak_signal_max_dated": weak_signal_max_dated,
        },
    }


def run(
    merge_state_path: str = "data/outputs/merge_state.json",
    output_path: str = "data/outputs/temporal_state.json",
    collection=None,
    **stats_kwargs,
) -> dict:
    """Read drivers + their chunk years from the KB, write the temporal profile.

    Years live in Chroma chunk metadata (``kb.py`` writes ``year`` there); one ``.get`` pulls
    every chunk's metadata (same pattern as ``trends.py``). Drivers without dated chunks fall
    through to ``emergence="unknown"``.
    """
    with open(merge_state_path) as f:
        drivers = json.load(f).get("unified_drivers", [])

    if collection is None or collection == "auto":
        from src.rag import get_collection
        collection = get_collection()

    res = collection.get(include=["metadatas"], limit=100000)
    cid_year: dict[str, int] = {}
    corpus_years: list[int] = []
    for cid, meta in zip(res.get("ids", []), res.get("metadatas") or []):
        y = _parse_year((meta or {}).get("year"))
        if y is not None:
            cid_year[cid] = y
            corpus_years.append(y)

    names = {d["id"]: d.get("name", d["id"]) for d in drivers}
    driver_years = {
        d["id"]: [cid_year[c] for c in d.get("source_chunk_ids", []) if c in cid_year]
        for d in drivers
    }

    stats = temporal_stats(driver_years, corpus_years, **stats_kwargs)
    for rec in stats["drivers"]:
        rec["name"] = names.get(rec["driver_id"], rec["driver_id"])
    stats["metadata"] = {"method": "corpus_year_profile", "n_drivers": len(drivers),
                         "n_dated_chunks": len(cid_year)}

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Temporal: {stats['verdict']} ({len(cid_year)} dated chunks) → {output_path}")
    return stats
