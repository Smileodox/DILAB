"""Build RAG-ready text documents from structured drivers identification output."""
from __future__ import annotations

import json
from typing import Any

from tdi.models.output import (
    ImpactTreeSection,
    KnowledgeGraphSection,
    RagContext,
    RagDocument,
    ResearchEvidence,
    SignalClassification,
    TechnologyIndustryClassification,
)


def _lines(*parts: str) -> str:
    return "\n".join(p for p in parts if p)


def build_rag_context(
    query: str,
    target_year: int,
    classification: TechnologyIndustryClassification,
    research: ResearchEvidence,
    signals: SignalClassification,
    graph: KnowledgeGraphSection,
    impact: ImpactTreeSection,
) -> RagContext:
    documents: list[RagDocument] = []

    # 1 — Classification
    class_lines = [
        f"Query: {query}",
        f"Target year: {target_year}",
        f"Regulatory domain: {classification.regulatory_domain}",
        f"Primary technology (M): {classification.primary_technology}",
        f"Main industry: {classification.main_industry}",
        f"Query intent: {classification.query_intent}",
        "",
        "Related technologies: " + ", ".join(classification.related_technologies),
        "Related industries: " + ", ".join(classification.related_industries),
        "",
        "Technology taxonomy (TOD):",
    ]
    for cat in classification.technology_categories:
        cat_name = cat.get("category") or cat.get("name", "")
        subs = cat.get("subcategories", [])
        sub_names = [s.get("name", "") for s in subs]
        class_lines.append(f"  - {cat_name}: {', '.join(sub_names)}")
    for ind in classification.affected_industries:
        name = ind.get("name", "")
        techs = [t.get("name", "") for t in ind.get("technologies", [])]
        class_lines.append(f"Industry {name}: {', '.join(techs)}")

    documents.append(RagDocument(
        id="tech_industry_classification",
        section="technology_industry_classification",
        title="Technology–Industry Classification",
        content=_lines(*class_lines),
        metadata={
            "primary_technology": classification.primary_technology,
            "main_industry": classification.main_industry,
        },
    ))

    # 2 — Research evidence
    paper_lines = [f"Research evidence ({len(research.papers)} arXiv papers):"]
    for p in research.papers[:12]:
        paper_lines.append(
            f"- [{p.get('technology', '')}] {p.get('title', '')} "
            f"({p.get('published', '')}) — {p.get('abstract', '')[:280]}…",
        )
    if research.entities:
        ents = ", ".join(f"{e.get('entity_type')}: {e.get('value')}" for e in research.entities[:30])
        paper_lines.extend(["", f"Extracted entities: {ents}"])
    if research.keywords:
        paper_lines.extend(["", f"Keywords: {', '.join(research.keywords[:25])}"])

    documents.append(RagDocument(
        id="research_evidence",
        section="research_evidence",
        title="arXiv Research & NLP Entities",
        content=_lines(*paper_lines),
        metadata={"paper_count": len(research.papers), "entity_count": len(research.entities)},
    ))

    # 3 — Signal classification
    signal_lines = [
        f"DVI signal classification ({signals.framework}):",
        f"Summary: {json.dumps(signals.summary)}",
        "",
    ]
    for sig in signals.signals:
        dvi = sig.get("dvi", {})
        signal_lines.append(
            f"- {sig.get('name')}: type={dvi.get('signal_type')}, "
            f"D={dvi.get('diffusion')}, V={dvi.get('visibility')}, I={dvi.get('impact')}, "
            f"composite={dvi.get('composite')}, papers={sig.get('paper_count', 0)}",
        )
    for stype, names in signals.by_signal_type.items():
        signal_lines.append(f"  {stype}: {', '.join(names)}")

    documents.append(RagDocument(
        id="signal_classification",
        section="signal_classification",
        title="DVI Signal Classification",
        content=_lines(*signal_lines),
        metadata=signals.summary,
    ))

    # 4 — Knowledge graph
    kg_lines = [
        f"Knowledge graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges.",
        f"Main technology: {graph.main_technology_label} (id={graph.main_technology_id})",
        f"Main industry: {graph.main_industry_label}",
        "",
        "Key relationships (probability ≥ 0.35):",
    ]
    for edge in sorted(graph.edges, key=lambda e: e.get("probability", 0), reverse=True)[:25]:
        src = next((n["label"] for n in graph.nodes if n["id"] == edge["source"]), edge["source"])
        tgt = next((n["label"] for n in graph.nodes if n["id"] == edge["target"]), edge["target"])
        kg_lines.append(
            f"- {src} —[{edge.get('relationship')}]→ {tgt} "
            f"(P={edge.get('probability', 0):.2f})",
        )
    if graph.propagation_paths:
        kg_lines.append("")
        kg_lines.append("Propagation paths:")
        for path in graph.propagation_paths[:8]:
            kg_lines.append(
                f"- {path.get('source_label')} → {' → '.join(path.get('path_labels', []))} "
                f"(cascade P={path.get('cascade_probability', 0):.2f})",
            )

    documents.append(RagDocument(
        id="knowledge_graph",
        section="knowledge_graph",
        title="Technology Knowledge Graph",
        content=_lines(*kg_lines),
        metadata=graph.statistics,
    ))

    # 5 — Impact tree
    impact_lines = [
        f"Impact tree evolution to {target_year}:",
        f"Paths: {impact.statistics.get('path_count', len(impact.evolution_paths))}, "
        f"Scenario seeds: {impact.statistics.get('scenario_seed_count', len(impact.scenario_seeds))}",
        "",
    ]
    for i, path in enumerate(
        sorted(
            impact.evolution_paths,
            key=lambda p: (
                bool(p.get("is_scenario_seed")),
                p.get("relation_probability") or 0,
            ),
            reverse=True,
        )[:16],
        1,
    ):
        techs = ", ".join(path.get("contributing_technologies") or [])
        impact_lines.append(
            f"Path {i} [{path.get('path_id', '')}]: "
            f"speed={path.get('evolution_speed')}, "
            f"KG P={path.get('relation_probability')}, "
            f"techs=[{techs}] → {path.get('final_outcome', '')}",
        )
    for seed in impact.scenario_seeds[:12]:
        impact_lines.append(
            f"SEED: {seed.get('evolved_outcome')} | cluster hint={seed.get('scenario_cluster_hint')} | "
            f"contributors={', '.join(seed.get('contributing_technologies') or [])}",
        )

    documents.append(RagDocument(
        id="impact_tree",
        section="impact_tree",
        title="Impact Tree & Evolution Paths",
        content=_lines(*impact_lines),
        metadata=impact.statistics,
    ))

    consolidated = "\n\n---\n\n".join(
        f"## {doc.title}\n{doc.content}" for doc in documents
    )

    return RagContext(documents=documents, consolidated_narrative=consolidated)
