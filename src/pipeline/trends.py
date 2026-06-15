"""Trend Scanning pipeline step: KB coverage-gap analysis.

Replaces hardcoded queries with a bottom-up approach:
  1. Fetch all trend-pool chunks from ChromaDB (with pre-computed embeddings)
  2. Embed BOM tech-driver descriptions to define the "covered" technology space
  3. Orphan chunks = trend chunks with max cosine-sim < threshold to any BOM driver
  4. KMeans-cluster orphans — each cluster represents a potential environmental dimension
  5. LLM extracts one driver name/description per cluster
  6. Post-filter: discard extracted drivers still too similar to BOM drivers

This generalizes to any KB / any domain — no hardcoded queries needed.

Input:  data/outputs/bom_state.json  (BOM tech drivers as coverage reference)
Output: data/outputs/trend_state.json
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np
from sklearn.cluster import KMeans

from src.llm import embed, safe_chat_json
from src.models.common import stable_id
from src.models.drivers import DriverConfidence, DriverOrigin, TechDriver
from src.prompts.trends import CLUSTER_DRIVER_EXTRACT
from src.rag import get_collection

log = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.55    # below → orphan (not covered by BOM)
BOM_OVERLAP_THRESHOLD = 0.70 # above → discard extracted driver (too close to BOM)
N_CLUSTERS = 12
MIN_CLUSTER_SIZE = 3
TOP_K_PER_CLUSTER = 5        # representative chunks sent to LLM per cluster


def _cosine_sim(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """(n, d) × (m, d) → (n, m) cosine similarity matrix."""
    An = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-10)
    Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-10)
    return An @ Bn.T


def run(
    bom_state_path: str = "data/outputs/bom_state.json",
    output_path: str = "data/outputs/trend_state.json",
    coverage_threshold: float = COVERAGE_THRESHOLD,
    bom_overlap_threshold: float = BOM_OVERLAP_THRESHOLD,
    n_clusters: int = N_CLUSTERS,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
) -> dict:
    # --- 1. Load BOM tech drivers (coverage reference) ---
    with open(bom_state_path) as f:
        bom_state = json.load(f)
    bom_drivers = bom_state.get("bom_drivers") or [
        n for n in bom_state.get("bom_nodes", {}).values() if n.get("is_tech_driver")
    ]
    if not bom_drivers:
        log.warning("No BOM tech drivers found — using all bom_nodes as fallback")
        bom_drivers = list(bom_state.get("bom_nodes", {}).values())
    print(f"  BOM tech drivers: {len(bom_drivers)}")

    bom_texts = [f"{n['name']}: {n.get('description', '')[:200]}" for n in bom_drivers]
    bom_embs = np.array(embed(bom_texts))
    print(f"  BOM embeddings computed: {bom_embs.shape}")

    # --- 2. Fetch trend-pool chunks from ChromaDB with stored embeddings ---
    collection = get_collection()
    result = collection.get(
        where={"pool": "trend"},
        include=["documents", "embeddings", "metadatas"],
        limit=10000,
    )

    chunk_ids: list[str] = result["ids"]
    chunk_docs: list[str] = result["documents"]
    chunk_metas: list[dict] = result["metadatas"]
    raw_embs = result.get("embeddings")

    if not chunk_ids:
        log.error("No trend-pool chunks found in ChromaDB")
        return {"trend_drivers": [], "all_trends_raw": [], "metadata": {"error": "no trend chunks"}}

    if raw_embs is None or len(raw_embs) == 0:
        print("  Embeddings not in ChromaDB — re-embedding trend chunks (one-time cost)...")
        chunk_embs = np.array(embed(chunk_docs))
    else:
        chunk_embs = np.array(raw_embs)

    print(f"  Trend chunks: {len(chunk_ids)}")

    # --- 3. Coverage mask ---
    sim_matrix = _cosine_sim(chunk_embs, bom_embs)  # (n_chunks, n_bom)
    max_bom_sim = sim_matrix.max(axis=1)             # (n_chunks,)

    orphan_mask = max_bom_sim < coverage_threshold
    n_covered = int((~orphan_mask).sum())
    n_orphan = int(orphan_mask.sum())
    print(f"  Coverage: {n_covered} covered by BOM, {n_orphan} orphans (threshold={coverage_threshold})")

    if n_orphan < min_cluster_size * 2:
        print("  WARNING: too few orphans — using all trend chunks for clustering")
        orphan_mask = np.ones(len(chunk_ids), dtype=bool)
        n_orphan = len(chunk_ids)

    indices = [i for i, m in enumerate(orphan_mask) if m]
    orphan_ids = [chunk_ids[i] for i in indices]
    orphan_docs = [chunk_docs[i] for i in indices]
    orphan_metas = [chunk_metas[i] for i in indices]
    orphan_embs = chunk_embs[np.array(indices)]

    # --- 4. KMeans cluster ---
    k = min(n_clusters, n_orphan // min_cluster_size)
    k = max(k, 2)
    print(f"  Clustering {n_orphan} orphan chunks → k={k}")

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(orphan_embs)
    centroids = kmeans.cluster_centers_

    # --- 5. Extract one driver per cluster via LLM ---
    extracted: list[TechDriver] = []

    for cluster_idx in range(k):
        c_mask_arr = labels == cluster_idx
        c_size = int(c_mask_arr.sum())
        if c_size < min_cluster_size:
            continue

        c_indices = [i for i, m in enumerate(c_mask_arr) if m]
        c_embs = orphan_embs[c_mask_arr]
        c_ids = [orphan_ids[i] for i in c_indices]
        c_docs = [orphan_docs[i] for i in c_indices]
        c_metas = [orphan_metas[i] for i in c_indices]

        # Top-K chunks closest to centroid
        centroid = centroids[cluster_idx]
        dists = np.linalg.norm(c_embs - centroid, axis=1)
        top_k = min(TOP_K_PER_CLUSTER, len(c_ids))
        top_idx = np.argsort(dists)[:top_k]

        chunks_text = "\n\n---\n\n".join(
            f"[Source: {c_metas[i].get('source_title', '?')}]\n{c_docs[i]}"
            for i in top_idx
        )

        llm_result = safe_chat_json(
            CLUSTER_DRIVER_EXTRACT.format(chunks_text=chunks_text),
            system="You are identifying external environmental drivers for a technology foresight study on regulatory spectrum monitoring.",
        )

        name = llm_result.get("name", "").strip()
        description = llm_result.get("description", "").strip()
        relevance = llm_result.get("relevance", "").strip()
        driver_type = llm_result.get("driver_type", "regulatory")

        if not name or not description:
            log.warning("Cluster %d: LLM returned empty name/description", cluster_idx)
            continue

        full_desc = f"{description} [Type: {driver_type}] {relevance}"
        driver = TechDriver(
            id=stable_id(name, "trend"),
            name=name,
            description=full_desc,
            origin=DriverOrigin.TREND,
            confidence=DriverConfidence.LOW,
            source_chunk_ids=c_ids,  # all cluster members, not just top-K
        )
        extracted.append(driver)
        print(f"  Cluster {cluster_idx:2d} ({c_size:4d} chunks) → {name[:65]}")

    print(f"  Extracted {len(extracted)} candidate drivers")

    # --- 6. Post-filter: discard drivers too similar to BOM ---
    if extracted:
        desc_texts = [f"{d.name}: {d.description[:200]}" for d in extracted]
        driver_embs = np.array(embed(desc_texts))
        bom_overlap = _cosine_sim(driver_embs, bom_embs).max(axis=1)

        final: list[TechDriver] = []
        for d, sim in zip(extracted, bom_overlap):
            if sim >= bom_overlap_threshold:
                print(f"  Dropped (BOM overlap={sim:.2f}): {d.name[:65]}")
            else:
                final.append(d)
        print(f"  After BOM filter: {len(final)} trend drivers retained")
    else:
        final = []

    state = {
        "trend_drivers": [d.model_dump(mode="json") for d in final],
        "all_trends_raw": [],  # schema compat with notebook output
        "metadata": {
            "method": "kb_coverage_gap",
            "n_trend_chunks": len(chunk_ids),
            "n_orphan_chunks": n_orphan,
            "coverage_threshold": coverage_threshold,
            "bom_overlap_threshold": bom_overlap_threshold,
            "n_clusters": k,
            "n_extracted": len(extracted),
            "n_final": len(final),
        },
    }

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    log.info("Trend state saved: %d drivers → %s", len(final), output_path)
    return state
