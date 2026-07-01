from tdi.models.schemas import ForesightResponse, QueryRequest
from tdi.services.llm_service import LLMService
from tdi.services.arxiv_service import ArxivService
from tdi.services.nlp_service import NLPService
from tdi.services.dvi_analyzer import DVIAnalyzer
from tdi.services.knowledge_graph import KnowledgeGraphBuilder
from tdi.services.impact_tree import ImpactTreeBuilder
from tdi.services.scenario_generator import ScenarioGenerator


class ForesightOrchestrator:
    def __init__(self):
        self.llm = LLMService()
        self.arxiv = ArxivService()
        self.nlp = NLPService()
        self.dvi = DVIAnalyzer()
        self.kg_builder = KnowledgeGraphBuilder()
        self.impact_builder = ImpactTreeBuilder()
        self.scenario_gen = ScenarioGenerator()

    async def run_analysis(self, request: QueryRequest) -> ForesightResponse:
        classification = await self.llm.classify_query(request.query)
        classification = self.llm.ensure_affected_industries(self.llm.ensure_hierarchy(classification))
        classification_json = self.llm.to_classification_json(classification)

        all_technologies = list(dict.fromkeys(
            [classification.primary_technology] + classification.related_technologies
        ))[: self.llm.settings.max_technologies]

        papers = await self.arxiv.fetch_papers_for_technologies(all_technologies)

        for paper in papers:
            paper.abstract = self.nlp.clean_text(paper.abstract)

        entities = self.nlp.extract_entities(papers)
        keywords = self.nlp.extract_keywords(papers)

        if papers:
            chunks = []
            for paper in papers:
                chunks.extend(self.nlp.chunk_text(paper.abstract))
            self.nlp.compute_embeddings(chunks[:20])

        signals = self.dvi.analyze_all(all_technologies, papers, entities, keywords)

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
        impact_tree = self.impact_builder.build(
            classification, signals, knowledge_graph, request.target_year,
        )
        scenarios = self.scenario_gen.generate(
            classification, signals, papers, request.target_year, impact_tree,
        )

        signal_dicts = [
            {"name": s.name, "dvi": s.dvi.model_dump(), "signal_type": s.dvi.signal_type.value}
            for s in signals
        ]
        paper_dicts = [p.model_dump() for p in papers]

        max_explanations = self.llm.settings.llm_max_scenario_explanations
        if max_explanations > 0:
            top_scenarios = [s.model_dump() for s in scenarios[:max_explanations]]
            explanations = await self.llm.explain_scenarios_batch(
                top_scenarios, paper_dicts, signal_dicts, request.target_year,
            )
            for scenario in scenarios[:max_explanations]:
                scenario.llm_explanation = explanations.get(scenario.id, scenario.description)

        recommendations = await self.llm.generate_recommendations(
            request.query,
            classification,
            scenarios,
            signal_dicts,
            request.target_year,
        )

        return ForesightResponse(
            query=request.query,
            target_year=request.target_year,
            classification=classification,
            classification_json=classification_json,
            papers=papers,
            signals=signals,
            knowledge_graph=knowledge_graph,
            impact_tree=impact_tree,
            scenarios=scenarios,
            strategic_recommendations=recommendations,
            processing_summary={
                "technologies_analyzed": len(all_technologies),
                "papers_retrieved": len(papers),
                "technology_categories": len(classification.technology_categories),
                "affected_industries": len(classification.affected_industries),
                "industry_technologies_total": sum(
                    len(ind.technologies) for ind in classification.affected_industries
                ),
                "subcategories_total": sum(
                    len(c.subcategories) for c in classification.technology_categories
                ),
                "entities_extracted": len(entities),
                "keywords_found": len(keywords),
                "graph_nodes": len(knowledge_graph.nodes),
                "graph_edges": len(knowledge_graph.edges),
                "scenarios_generated": len(scenarios),
            },
        )
