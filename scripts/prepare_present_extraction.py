"""Data prep for the /present extraction-mechanism scene (point cloud).

No reproduction needed: the final run persisted the exact cluster memberships —
every trend driver in trend_state.json carries ``source_chunk_ids`` = ALL member
chunks of the KMeans sub-cluster it was named from (see trends.py::_extract_driver).
So the per-chunk assignment (orphan/covered, dimension, cluster) is read straight
from the artifact; only the 2D layout is computed here, via PCA over the chunk
embeddings already stored in ChromaDB. Zero LLM/embedding calls, fully offline.

Output: data/outputs/present_extraction.json
  meta      — copy of trend_state metadata + artifact-consistency checks
  points    — ~600 sampled chunks: {x, y, covered, dim, cluster}  (PCA 2D, [0,1])
  clusters  — 19 clusters: {key, dim, name, n_chunks, cx, cy, unified_id,
              selected, is_journey}

Run:  uv run python scripts/prepare_present_extraction.py
"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag import get_collection  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "outputs")
JOURNEY_DRIVER_ID = "f33ab61e5a83"  # mirror web/app.py::_PRESENT_DRIVER_ID
N_COVERED_SAMPLE = 150
N_ORPHAN_SAMPLE = 450
MIN_PER_CLUSTER = 8


def _p(name):
    return os.path.join(OUT, name)


def _pca2(x: np.ndarray) -> np.ndarray:
    """Deterministic 2D PCA via SVD (same approach as prepare_present_data)."""
    xc = x - x.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(xc, full_matrices=False)
    return xc @ vt[:2].T


def main() -> None:
    trend_state = json.load(open(_p("trend_state.json")))
    published = trend_state["metadata"]
    merge = json.load(open(_p("merge_state.json")))
    cib_ids = set(json.load(open(_p("cib_state.json")))["driver_ids"])
    bom_state = json.load(open(_p("bom_state.json")))

    # --- Cluster membership straight from the run artifact -----------------------
    unified_by_ids = [(set(d.get("source_chunk_ids", [])), d) for d in merge["unified_drivers"]]
    clusters: list[dict] = []
    cluster_of: dict[str, int] = {}  # chunk id -> cluster index
    for d in trend_state["trend_drivers"]:
        member_set = set(d["source_chunk_ids"])
        # selected/journey flags live on the post-merge unified driver; trend ids
        # usually survive the merge unchanged, so try id first, overlap as fallback.
        uni = next((u for _, u in unified_by_ids if u["id"] == d["id"]), None)
        if uni is None:
            uni = max(unified_by_ids, default=(0, None),
                      key=lambda t: len(member_set & t[0]))[1]
        for cid in member_set:
            cluster_of[cid] = len(clusters)
        clusters.append({
            "key": d["id"], "dim": d["dimension_type"], "name": d["name"],
            "n_chunks": len(member_set),
            "unified_id": uni["id"] if uni else None,
            "selected": bool(uni and uni["id"] in cib_ids),
            "is_journey": bool(uni and uni["id"] == JOURNEY_DRIVER_ID),
        })

    # --- Layout: PCA over the stored embeddings of all trend-pool chunks ---------
    collection = get_collection()
    result = collection.get(where={"pool": "trend"}, include=["embeddings"], limit=10000)
    chunk_ids = result["ids"]
    coords = _pca2(np.array(result["embeddings"]))
    lo, hi = coords.min(axis=0), coords.max(axis=0)
    coords = (coords - lo) / np.maximum(hi - lo, 1e-9)
    pos_by_chunk = {cid: i for i, cid in enumerate(chunk_ids)}

    # --- Consistency checks: artifact memberships vs published aggregates --------
    missing = [cid for cid in cluster_of if cid not in pos_by_chunk]
    dim_counts: dict[str, int] = {}
    for c in clusters:
        dim_counts[c["dim"]] = dim_counts.get(c["dim"], 0) + c["n_chunks"]
    checks = {
        "n_trend_chunks": len(chunk_ids) == published["n_trend_chunks"],
        "n_orphan_chunks": len(cluster_of) == published["n_orphan_chunks"],
        "bucket_sizes": dim_counts == published["dimension_bucket_sizes"],
        "n_clusters": len(clusters) == published["n_sub_clusters"],
        "chunks_resolved": not missing,
    }
    print(f"trend chunks in Chroma: {len(chunk_ids)} (published {published['n_trend_chunks']})")
    print(f"clustered chunks from artifact: {len(cluster_of)} "
          f"(published orphans {published['n_orphan_chunks']}, unresolved {len(missing)})")
    for name, ok in checks.items():
        print(f"  check {name}: {'OK' if ok else 'MISMATCH'}")
    print(f"  journey cluster: "
          f"{next((c['name'] for c in clusters if c['is_journey']), 'NOT FOUND')}")

    member_pos: list[list[int]] = [[] for _ in clusters]
    for cid, ci in cluster_of.items():
        if cid in pos_by_chunk:
            member_pos[ci].append(pos_by_chunk[cid])
    for c, mp in zip(clusters, member_pos):
        cc = coords[np.array(mp)].mean(axis=0)
        c["cx"], c["cy"] = round(float(cc[0]), 4), round(float(cc[1]), 4)

    # --- Deterministic sampling: ~150 covered + ~450 orphans (per-cluster strata) -
    rng = random.Random(42)
    covered_pos = [i for i, cid in enumerate(chunk_ids) if cid not in cluster_of]
    covered_sample = (rng.sample(covered_pos, N_COVERED_SAMPLE)
                      if len(covered_pos) > N_COVERED_SAMPLE else covered_pos)

    def _pt(i, covered, c=None):
        return {"x": round(float(coords[i][0]), 4), "y": round(float(coords[i][1]), 4),
                "covered": covered, "dim": c["dim"] if c else None,
                "cluster": c["key"] if c else None}

    points = [_pt(i, True) for i in covered_sample]
    n_orphan = len(cluster_of)
    for c, mp in zip(clusters, member_pos):
        take = max(MIN_PER_CLUSTER, round(N_ORPHAN_SAMPLE * c["n_chunks"] / max(n_orphan, 1)))
        chosen = rng.sample(mp, take) if len(mp) > take else mp
        points.extend(_pt(i, False, c) for i in chosen)

    meta = dict(published)
    meta["reproduction_ok"] = all(checks.values())
    meta["n_points_sampled"] = len(points)
    meta["n_covered_sampled"] = len(covered_sample)
    meta["n_bom_drivers"] = len(bom_state.get("bom_drivers", []))

    with open(_p("present_extraction.json"), "w") as f:
        json.dump({"meta": meta, "points": points, "clusters": clusters}, f, indent=2)
    print(f"saved -> present_extraction.json ({len(points)} points, {len(clusters)} clusters, "
          f"consistency_ok={meta['reproduction_ok']})")


if __name__ == "__main__":
    main()
