"""Technology Drivers Identification pipeline — steps 1–6 (through impact tree)."""
from __future__ import annotations

from tdi.models.output import (
    IdentificationInput,
    ImpactTreeSection,
    KnowledgeGraphSection,
    ResearchEvidence,
    SignalClassification,
    TechnologyDriversIdentificationOutput,
    TechnologyIndustryClassification,
)
from tdi.models.schemas import QueryRequest
from tdi.rag_builder import build_rag_context
from tdi.serializers import (
    extract_evolution_paths,
    group_signals_by_type,
    impact_node_to_dict,
    scenario_seed_to_dict,
    signal_summary,
)
from tdi.services.arxiv_service import ArxivService
from tdi.services.dvi_analyzer import DVIAnalyzer
from tdi.services.impact_tree import ImpactTreeBuilder
from tdi.services.knowledge_graph import KnowledgeGraphBuilder
from tdi.services.llm_service import LLMService
from tdi.services.nlp_service import NLPService


class TechnologyDriversIdentificationPipeline:
    """
    Pipeline step 1: identify technology drivers from a foresight query.

    Produces a structured JSON artifact (with RAG text chunks) containing:
      - Technology–Industry Classification (LLM / TOD)
      - Research evidence (arXiv + NLP)
      - Signal classification (DVI)
      - Knowledge graph
      - Impact tree
    """

    def __init__(self) -> None:
        self.llm = LLMService()
        self.arxiv = ArxivService()
        self.nlp = NLPService()
        self.dvi = DVIAnalyzer()
        self.kg_builder = KnowledgeGraphBuilder()
        self.impact_builder = ImpactTreeBuilder()

    async def run(
        self,
        query: str,
        target_year: int = 2035,
    ) -> TechnologyDriversIdentificationOutput:
        request = QueryRequest(query=query.strip(), target_year=target_year)
        inp = IdentificationInput(query=request.query, target_year=request.target_year)

        classification = await self.llm.classify_query(request.query)
        classification = self.llm.ensure_affected_industries(
            self.llm.ensure_hierarchy(classification),
        )
        classification_json = self.llm.to_classification_json(classification)

        all_technologies = list(dict.fromkeys(
            [classification.primary_technology] + classification.related_technologies,
        ))[: self.llm.settings.max_technologies]

        tech_industry = TechnologyIndustryClassification(
            regulatory_domain=classification.regulatory_domain,
            primary_technology=classification.primary_technology,
            primary_category=classification.primary_category,
            main_industry=classification.main_industry,
            query_intent=classification.query_intent,
            related_technologies=classification.related_technologies,
            related_industries=classification.related_industries,
            technology_categories=classification_json.get("technology_categories", []),
            affected_industries=classification_json.get("affected_industries", []),
            main_industry_technologies=classification_json.get("main_industry_technologies", []),
            llm_classification_raw=classification_json,
        )

        papers = await self.arxiv.fetch_papers_for_technologies(all_technologies)
        for paper in papers:
            paper.abstract = self.nlp.clean_text(paper.abstract)

        entities = self.nlp.extract_entities(papers)
        keywords = self.nlp.extract_keywords(papers)

        if papers:
            chunks: list[str] = []
            for paper in papers:
                chunks.extend(self.nlp.chunk_text(paper.abstract))
            self.nlp.compute_embeddings(chunks[:20])

        research = ResearchEvidence(
            papers=[p.model_dump(mode="json") for p in papers],
            entities=[e.model_dump(mode="json") for e in entities],
            keywords=keywords,
        )

        signals = self.dvi.analyze_all(all_technologies, papers, entities, keywords)
        signal_section = SignalClassification(
            signals=[s.model_dump(mode="json") for s in signals],
            by_signal_type=group_signals_by_type(signals),
            summary=signal_summary(signals),
        )

        embeddings: dict[str, list[float]] = {}
        if papers:
            paper_texts = [p.abstract for p in papers]
            paper_embs = self.nlp.compute_embeddings(paper_texts)
            for paper, emb in zip(papers, paper_embs):
                embeddings[paper.arxiv_id] = emb
            center_text = (
                f"{classification.regulatory_domain} "
                f"{' '.join(classification.related_industries[:3])} "
                f"{classification.primary_technology}"
            )
            embeddings["__center__"] = self.nlp.compute_embeddings([center_text])[0]

        knowledge_graph = self.kg_builder.build(
            classification, signals, entities, papers, embeddings=embeddings,
        )
        kg_section = KnowledgeGraphSection(
            nodes=[n.model_dump(mode="json") for n in knowledge_graph.nodes],
            edges=[e.model_dump(mode="json") for e in knowledge_graph.edges],
            propagation_paths=[
                p.model_dump(mode="json") for p in knowledge_graph.propagation_paths
            ],
            main_technology_id=knowledge_graph.main_technology_id,
            main_technology_label=knowledge_graph.main_technology_label,
            main_industry_id=knowledge_graph.main_industry_id,
            main_industry_label=knowledge_graph.main_industry_label,
            statistics={
                "node_count": len(knowledge_graph.nodes),
                "edge_count": len(knowledge_graph.edges),
                "propagation_path_count": len(knowledge_graph.propagation_paths),
                "node_types": list({n.node_type for n in knowledge_graph.nodes}),
            },
        )

        impact_tree = self.impact_builder.build(
            classification, signals, knowledge_graph, request.target_year,
        )
        evolution_paths = extract_evolution_paths(impact_tree)
        scenario_seeds = [
            scenario_seed_to_dict(n)
            for n in ImpactTreeBuilder.extract_scenario_seeds(impact_tree)
        ]
        seed_paths = [p for p in evolution_paths if p.get("is_scenario_seed")]

        impact_section = ImpactTreeSection(
            tree=impact_node_to_dict(impact_tree),
            evolution_paths=evolution_paths,
            scenario_seeds=scenario_seeds,
            statistics={
                "path_count": len(evolution_paths),
                "scenario_seed_count": len(scenario_seeds),
                "seed_path_count": len(seed_paths),
                "base_year": 2026,
                "target_year": request.target_year,
            },
        )

        processing_summary = {
            "technologies_analyzed": len(all_technologies),
            "papers_retrieved": len(papers),
            "technology_categories": len(classification.technology_categories),
            "affected_industries": len(classification.affected_industries),
            "entities_extracted": len(entities),
            "keywords_found": len(keywords),
            "signals_classified": len(signals),
            "graph_nodes": len(knowledge_graph.nodes),
            "graph_edges": len(knowledge_graph.edges),
            "impact_paths": len(evolution_paths),
            "scenario_seeds": len(scenario_seeds),
        }

        rag_context = build_rag_context(
            query=request.query,
            target_year=request.target_year,
            classification=tech_industry,
            research=research,
            signals=signal_section,
            graph=kg_section,
            impact=impact_section,
        )

        return TechnologyDriversIdentificationOutput(
            input=inp,
            technology_industry_classification=tech_industry,
            research_evidence=research,
            signal_classification=signal_section,
            knowledge_graph=kg_section,
            impact_tree=impact_section,
            processing_summary=processing_summary,
            rag_context=rag_context,
        )
