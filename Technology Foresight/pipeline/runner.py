"""Orchestrate the full foresight pipeline."""
from __future__ import annotations

from typing import Any

from storage.graph_store import load_job_meta, save_progress, save_result
from pipeline.ingest import merge_corpus
from pipeline.embed import embed_texts
from pipeline.cluster import run_clustering
from pipeline.evolution import detect_change_events, detect_weak_signals, STAGE_COLORS
from pipeline.reasoning import (
    extract_sao_triples,
    explain_change_events,
    build_influence_graph,
    lifecycle_llm_blurb,
)
from pipeline.scenario import extract_uncertainty_drivers, generate_scenarios, build_impact_trees


def run_pipeline(job_id: str, documents: list[dict]) -> dict[str, Any]:
    stages = [
        ("ingesting", 5, "Ingesting documents…"),
        ("embedding", 20, "Embedding with SBERT…"),
        ("clustering", 40, "Clustering with BERTopic…"),
        ("evolution", 55, "Computing evolution…"),
        ("reasoning", 75, "LLM reasoning…"),
        ("scenarios", 90, "Building scenarios & LLM impact rationales…"),
        ("done", 100, "Done"),
    ]

    def progress(idx: int):
        _, pct, label = stages[idx]
        save_progress(job_id, stages[idx][0], pct, label)

    progress(0)
    job_meta = load_job_meta(job_id)
    foresight = job_meta.get("foresight") or {}

    texts = [d.get("text") or d.get("abstract", "") or d.get("title", "") for d in documents]
    for i, d in enumerate(documents):
        d["doc_index"] = i

    progress(1)
    embeddings = embed_texts(texts)

    progress(2)
    cluster_out = run_clustering(texts, embeddings)
    topics = cluster_out["topics"]
    clusters = cluster_out["clusters"]

    for i, d in enumerate(documents):
        d["topic_id"] = topics[i]

    progress(3)
    evo_bundle, events = detect_change_events(documents, topics, clusters)
    weak_signals = detect_weak_signals(evo_bundle["timeline"], clusters)

    progress(4)
    sao = extract_sao_triples(texts, topics)
    influence = build_influence_graph(clusters, documents, foresight=foresight)
    events_enriched = explain_change_events(
        events,
        clusters,
        influence=influence,
        lifecycle=evo_bundle.get("lifecycle", {}),
        foresight=foresight,
    )

    lifecycle_blurbs = {}
    for c in clusters:
        tid = c["topic_id"]
        lc = evo_bundle["lifecycle"].get(str(tid), {})
        stage = lc.get("stage", "introduction")
        lifecycle_blurbs[str(tid)] = lifecycle_llm_blurb(
            stage, c.get("keywords", []), label=c.get("label", "")
        )

    cluster_details = []
    for c in clusters:
        tid = c["topic_id"]
        doc_idxs = [i for i, t in enumerate(topics) if t == tid]
        src_b = {"scholar": 0, "uploaded": 0}
        for i in doc_idxs:
            s = documents[i].get("source", "uploaded")
            src_b[s] = src_b.get(s, 0) + 1
        lc = evo_bundle["lifecycle"].get(str(tid), {})
        cluster_details.append(
            {
                **c,
                "lifecycle_stage": lc.get("stage", "introduction"),
                "stage_color": STAGE_COLORS.get(lc.get("stage", "introduction"), "#6B7280"),
                "lifecycle_explanation": lc.get("explanation", ""),
                "lifecycle_llm": lifecycle_blurbs.get(str(tid), ""),
                "source_breakdown": src_b,
                "doc_indices": doc_idxs,
            }
        )

    progress(5)
    drivers = extract_uncertainty_drivers(events_enriched, cluster_details)
    scenario_bundle = generate_scenarios(drivers, cluster_details, events_enriched, foresight=foresight)
    impact_trees = build_impact_trees(
        scenario_bundle,
        cluster_details,
        lifecycle=evo_bundle.get("lifecycle", {}),
        timeline=evo_bundle.get("timeline", {}),
        events=events_enriched,
        influence=influence,
        weak_signals=weak_signals,
        foresight=foresight,
    )

    progress(6)

    source_breakdown = {"scholar": 0, "uploaded": 0}
    for d in documents:
        src = d.get("source", "uploaded")
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    scatter_docs = []
    for p in cluster_out["points"]:
        d = documents[p["doc_index"]]
        scatter_docs.append(
            {
                **p,
                "title": d.get("title", "")[:80],
                "source": d.get("source", "uploaded"),
                "year": d.get("year"),
            }
        )

    result = {
        "job_id": job_id,
        "foresight": foresight,
        "scholar_query": job_meta.get("scholar_query", ""),
        "document_count": len(documents),
        "documents": [
            {
                "title": d.get("title"),
                "source": d.get("source"),
                "year": d.get("year"),
                "topic_id": d.get("topic_id"),
                "paper_id": d.get("paper_id", ""),
            }
            for d in documents
        ],
        "clusters": cluster_details,
        "scatter": {
            "points": scatter_docs,
            "why": cluster_out["why"],
        },
        "evolution": {
            **evo_bundle,
            "events": events_enriched,
            "weak_signals": weak_signals,
        },
        "reasoning": {
            "influence": influence,
            "sao": sao,
            "why_influence": "Edges represent enabling or displacing relationships inferred from cluster themes and LLM foresight reasoning.",
        },
        "scenarios": {
            **scenario_bundle,
            "impact_trees": impact_trees,
        },
        "source_breakdown": source_breakdown,
    }

    save_result(job_id, result)
    return result
