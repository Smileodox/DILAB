"""Trend Scanning pipeline step: KB coverage-gap analysis.

Replaces hardcoded queries with a bottom-up approach:
  1. Fetch all trend-pool chunks from ChromaDB (with pre-computed embeddings)
  2. Embed BOM tech-driver descriptions to define the "covered" technology space
  3. Orphan chunks = trend chunks with max cosine-sim < threshold to any BOM driver
  4. Bucket orphans by nearest driving-dimension anchor, then KMeans-cluster WITHIN each bucket
  5. LLM extracts one driver per sub-cluster, stamped with its driving dimension_type
  6. Post-filter: discard extracted drivers still too similar to BOM drivers

This generalizes to any KB / any domain — no hardcoded queries needed.

Input:  data/outputs/bom_state.json  (BOM tech drivers as coverage reference)
Output: data/outputs/trend_state.json
"""
from __future__ import annotations

import json
import logging
import os
import random

import numpy as np
from sklearn.cluster import KMeans

from src.llm import embed, safe_chat_json
from src.models.common import stable_id
from src.models.drivers import DimensionType, DriverConfidence, DriverOrigin, TechDriver
from src.models.domain import DomainProfile
from src.prompts.trends import CLUSTER_DRIVER_EXTRACT
from src.rag import get_collection

log = logging.getLogger(__name__)

COVERAGE_THRESHOLD = 0.55    # below → orphan (not covered by BOM)
BOM_OVERLAP_THRESHOLD = 0.70 # above → discard extracted driver (too close to BOM)
MIN_CLUSTER_SIZE = 3
TOP_K_PER_CLUSTER = 5        # representative chunks sent to LLM per cluster
MAX_CHUNKS_PER_SOURCE = 150  # cap any single source's share of the orphan pool (mega-doc guard)
# Sub-cluster granularity is set PER BUCKET by its own richness (bucket_size / target), not by a
# single global budget split across dimensions. A rich bucket (e.g. hundreds of AI/RIS/quantum
# chunks) then yields several DISTINCT sub-theme drivers instead of collapsing to one paraphrase;
# MAX_DRIVERS_PER_DIM caps a huge bucket so it can't flood the field.
TARGET_CHUNKS_PER_DRIVER = 90
MAX_DRIVERS_PER_DIM = 6

# Generic (domain-neutral) DRIVING uncertainty dimensions. Orphan chunks are bucketed to their
# nearest anchor BEFORE clustering, then extraction runs per dimension — so the trend layer
# yields DISTINCT driving axes (regulatory / market / geopolitical / technological) instead of a
# single-dimension monoculture that later collapses to one blob in merge consolidation. This is the
# primary lever for scenario differentiation (raises the independent driving-axis count).
# `technological` = EXTERNAL tech-push trends (AI/ML, new methods) — exogenous, hence a driving axis,
# distinct from the endogenous hardware/software the BOM (product) is built from.
DRIVING_DIMENSIONS: dict[str, str] = {
    "regulatory": "regulation, standards, compliance, policy, mandates, certification, governance rules",
    "market": "market demand, adoption, competition, pricing, commercial deployment, customer and industry needs",
    "geopolitical": "national sovereignty, geopolitics, international coordination, security, trade restrictions",
    "technological": "technological breakthroughs, emerging methods, research and development, artificial intelligence and machine learning, automation, novel architectures, scientific innovation",
}


def _cosine_sim(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """(n, d) × (m, d) → (n, m) cosine similarity matrix."""
    An = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-10)
    Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-10)
    return An @ Bn.T


def _cap_per_source(ids, docs, metas, embs, cap, seed=42):
    """Subsample so no single ``source_title`` exceeds ``cap`` chunks.

    A mega-doc (e.g. a huge regulatory PDF that is 500+ chunks) would otherwise dominate the
    orphan pool by sheer mass and drown the smaller driving dimensions — the extracted
    market/geopolitical drivers then just paraphrase the mega-doc. Capping is domain-agnostic:
    it caps whichever source is over-represented, not any named document. Deterministic (seeded).
    """
    if not cap or cap <= 0:
        return ids, docs, metas, embs
    rng = random.Random(seed)
    by_source: dict[str, list[int]] = {}
    for i, m in enumerate(metas):
        by_source.setdefault(m.get("source_title", "?"), []).append(i)
    keep: list[int] = []
    for idxs in by_source.values():
        keep.extend(rng.sample(idxs, cap) if len(idxs) > cap else idxs)
    keep.sort()
    return (
        [ids[i] for i in keep],
        [docs[i] for i in keep],
        [metas[i] for i in keep],
        embs[np.array(keep)],
    )


def run(
    bom_state_path: str = "data/outputs/bom_state.json",
    output_path: str = "data/outputs/trend_state.json",
    coverage_threshold: float = COVERAGE_THRESHOLD,
    bom_overlap_threshold: float = BOM_OVERLAP_THRESHOLD,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    max_chunks_per_source: int = MAX_CHUNKS_PER_SOURCE,
    target_chunks_per_driver: int = TARGET_CHUNKS_PER_DRIVER,
    max_drivers_per_dim: int = MAX_DRIVERS_PER_DIM,
    profile: DomainProfile | None = None,
) -> dict:
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    pkw = profile.prompt_kwargs()
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

    # Cap over-represented sources so a mega-doc can't dominate the orphan pool and drown dimensions.
    n_before_cap = len(orphan_ids)
    orphan_ids, orphan_docs, orphan_metas, orphan_embs = _cap_per_source(
        orphan_ids, orphan_docs, orphan_metas, orphan_embs, max_chunks_per_source
    )
    n_orphan = len(orphan_ids)
    if n_orphan < n_before_cap:
        print(f"  Source cap ({max_chunks_per_source}/source): {n_before_cap} → {n_orphan} orphan chunks")

    # --- 4. Bucket orphans by driving dimension, then cluster WITHIN each bucket ---
    # Each orphan chunk is assigned to its nearest generic driving-dimension anchor, then
    # extraction runs per bucket so DISTINCT driving axes (regulatory / market / geopolitical /
    # technological) survive merge consolidation instead of collapsing into one monoculture blob.
    anchor_names = list(DRIVING_DIMENSIONS.keys())
    anchor_embs = np.array(embed(list(DRIVING_DIMENSIONS.values())))  # (n_dim, d)
    bucket_assign = _cosine_sim(orphan_embs, anchor_embs).argmax(axis=1)  # (n_orphan,) → dim index

    # --- 5. Extract drivers per dimension via LLM ---
    extracted: list[TechDriver] = []
    bucket_sizes: dict[str, int] = {}
    dim_driver_counts: dict[str, int] = {}
    total_sub_clusters = 0

    def _extract_driver(member_idxs: np.ndarray, center_emb: np.ndarray, dim_name: str) -> TechDriver | None:
        """Build one TechDriver from orphan-index members, LLM-summarized around center_emb.

        member_idxs: int array indexing the orphan_* arrays. source_chunk_ids records ALL members;
        only the top-K nearest center_emb are sent to the LLM as representative context.
        """
        member_embs = orphan_embs[member_idxs]
        dists = np.linalg.norm(member_embs - center_emb, axis=1)
        top_k = min(TOP_K_PER_CLUSTER, len(member_idxs))
        top_local = np.argsort(dists)[:top_k]
        top_orphan = [int(member_idxs[t]) for t in top_local]

        chunks_text = "\n\n---\n\n".join(
            f"[Source: {orphan_metas[o].get('source_title', '?')}]\n{orphan_docs[o]}"
            for o in top_orphan
        )

        llm_result = safe_chat_json(
            CLUSTER_DRIVER_EXTRACT.format(chunks_text=chunks_text, **pkw),
            system=(f"You are identifying {dim_name} environmental drivers "
                    f"for a technology foresight study on {pkw['domain']}."),
        )

        name = llm_result.get("name", "").strip()
        description = llm_result.get("description", "").strip()
        relevance = llm_result.get("relevance", "").strip()
        driver_type = llm_result.get("driver_type", dim_name)

        if not name or not description:
            log.warning("Bucket %s: LLM returned empty name/description", dim_name)
            return None

        full_desc = f"{description} [Type: {driver_type}] {relevance}"
        return TechDriver(
            id=stable_id(name, "trend"),
            name=name,
            description=full_desc,
            origin=DriverOrigin.TREND,
            confidence=DriverConfidence.LOW,
            dimension_type=DimensionType(dim_name),  # stamps the driving axis so it survives merge
            source_chunk_ids=[orphan_ids[int(o)] for o in member_idxs],  # all members, not just top-K
        )

    for dim_i, dim_name in enumerate(anchor_names):
        bucket_idxs = np.where(bucket_assign == dim_i)[0]  # orphan-index ints
        bucket_size = int(bucket_idxs.size)
        bucket_sizes[dim_name] = bucket_size
        dim_driver_counts[dim_name] = 0
        if bucket_size == 0:
            print(f"  [{dim_name:12s}] empty bucket — skipped")
            continue

        bucket_embs = orphan_embs[bucket_idxs]
        # Granularity by the bucket's OWN richness (÷ target), bounded by viable sub-clusters and a
        # per-dimension ceiling — so a rich bucket surfaces distinct sub-themes, not one paraphrase.
        k_dim = max(1, min(
            round(bucket_size / target_chunks_per_driver),
            max(1, bucket_size // min_cluster_size),
            max_drivers_per_dim,
        ))
        print(f"  [{dim_name:12s}] {bucket_size} chunks → k_dim={k_dim}")

        n_before = len(extracted)

        if k_dim == 1:
            d = _extract_driver(bucket_idxs, bucket_embs.mean(axis=0), dim_name)
            if d:
                extracted.append(d)
            total_sub_clusters += 1
        else:
            km = KMeans(n_clusters=k_dim, random_state=42, n_init=10)
            sub_labels = km.fit_predict(bucket_embs)
            for sub in range(k_dim):
                sub_local = np.where(sub_labels == sub)[0]  # positions within the bucket
                if sub_local.size == 0:
                    continue
                sub_idxs = bucket_idxs[sub_local]  # back to orphan-index ints
                total_sub_clusters += 1
                d = _extract_driver(sub_idxs, km.cluster_centers_[sub], dim_name)
                if d:
                    extracted.append(d)

        # Guarantee >=1 driver per non-empty dimension (covers all-empty-LLM / small-bucket cases)
        if len(extracted) == n_before:
            d = _extract_driver(bucket_idxs, bucket_embs.mean(axis=0), dim_name)
            if d:
                extracted.append(d)
                total_sub_clusters += 1

        dim_driver_counts[dim_name] = len(extracted) - n_before
        print(f"  [{dim_name:12s}] emitted {dim_driver_counts[dim_name]} driver(s)")

    n_dims_nonempty = sum(1 for v in bucket_sizes.values() if v)
    print(f"  Extracted {len(extracted)} candidate drivers across {n_dims_nonempty} dimensions")

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
            "method": "kb_coverage_gap_dimension_bucketed",
            "n_trend_chunks": len(chunk_ids),
            "n_orphan_chunks": n_orphan,
            "coverage_threshold": coverage_threshold,
            "bom_overlap_threshold": bom_overlap_threshold,
            "max_chunks_per_source": max_chunks_per_source,
            "target_chunks_per_driver": target_chunks_per_driver,
            "max_drivers_per_dim": max_drivers_per_dim,
            "dimension_bucket_sizes": bucket_sizes,      # {dim: chunk count, incl 0}
            "dimension_driver_counts": dim_driver_counts,  # {dim: drivers emitted}
            "n_sub_clusters": total_sub_clusters,
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
