import hashlib
from tdi.models.schemas import (
    ClassificationResult,
    ExtractedEntity,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    SubCategoryAssignment,
    TechnologySignal,
    ArxivPaper,
)
from tdi.services.ml_probability import edge_probability_ml


class KnowledgeGraphBuilder:
    """
    Structured knowledge graph from LLM classification:
      - Main Industry (yellow, center)
      - Related industries (green) → Main Industry
      - Main-industry technologies (blue) → Main Industry / M
      - Industry-specific technologies (red) → Related Industry
    """

    def _node_id(self, label: str, node_type: str) -> str:
        return hashlib.md5(f"{node_type}:{label}".encode()).hexdigest()[:12]

    def _main_industry_name(self, classification: ClassificationResult) -> str:
        if classification.main_industry.strip():
            return classification.main_industry.strip()
        return "telecommunications"

    def _related_industry_names(
        self, classification: ClassificationResult, main_industry: str,
    ) -> list[str]:
        names: list[str] = []
        seen: set[str] = {main_industry.lower()}

        for ind in classification.affected_industries:
            if ind.name.lower() not in seen and not ind.is_main:
                seen.add(ind.name.lower())
                names.append(ind.name)

        for ind in classification.related_industries:
            if ind.lower() not in seen and ind.lower() != main_industry.lower():
                seen.add(ind.lower())
                names.append(ind)

        return names

    def _industry_tech_map(self, classification: ClassificationResult) -> dict[str, list]:
        """Related industries only — main industry techs are blue tier."""
        mapping: dict[str, list] = {}
        for ind in classification.affected_industries:
            if ind.is_main:
                continue
            if ind.technologies:
                mapping[ind.name] = ind.technologies
        return mapping

    def _main_industry_techs(self, classification: ClassificationResult) -> list:
        if classification.main_industry_technologies:
            return classification.main_industry_technologies
        for ind in classification.affected_industries:
            if ind.is_main and ind.technologies:
                return ind.technologies
        return []

    def _taxonomy_techs(self, classification: ClassificationResult) -> list:
        """Subcategories from TOD taxonomy (blue tier), plus main-industry technologies."""
        industry_tech_names = {
            t.name.lower()
            for techs in self._industry_tech_map(classification).values()
            for t in techs
        }
        main_industry_tech_names = {
            t.name.lower() for t in self._main_industry_techs(classification)
        }
        primary = classification.primary_technology.lower()
        out = []
        seen: set[str] = set()

        for cat in classification.technology_categories:
            for sub in cat.subcategories:
                key = sub.name.lower()
                if key in seen or key in industry_tech_names:
                    continue
                seen.add(key)
                out.append(sub)

        for tech in self._main_industry_techs(classification):
            key = tech.name.lower()
            if key in seen or key == primary or key in industry_tech_names:
                continue
            seen.add(key)
            out.append(SubCategoryAssignment(
                name=tech.name,
                confidence=tech.confidence,
                relationship=tech.relationship,
                direction=tech.direction,
            ))

        if primary not in seen:
            out.insert(0, SubCategoryAssignment(
                name=classification.primary_technology,
                confidence=0.92,
                relationship="coexists_with",
                direction="is_main",
            ))

        return out

    def _co_occurrence(self, term_a: str, term_b: str, papers: list[ArxivPaper]) -> float:
        count = sum(
            1 for p in papers
            if term_a.lower() in (p.title + p.abstract).lower()
            and term_b.lower() in (p.title + p.abstract).lower()
        )
        return count / max(len(papers), 1)

    def _edge_prob(
        self,
        confidence: float,
        relationship: str,
        papers: list[ArxivPaper],
        source_label: str,
        target_label: str,
        signal_map: dict[str, TechnologySignal],
    ) -> float:
        src_sig = signal_map.get(source_label.lower())
        tgt_sig = signal_map.get(target_label.lower())
        return edge_probability_ml(
            source_dvi=src_sig.dvi.composite if src_sig else confidence,
            target_dvi=tgt_sig.dvi.composite if tgt_sig else confidence,
            co_occurrence=self._co_occurrence(source_label, target_label, papers),
            relationship=relationship,
        )

    def build(
        self,
        classification: ClassificationResult,
        signals: list[TechnologySignal],
        entities: list[ExtractedEntity],
        papers: list[ArxivPaper],
        embeddings: dict[str, list[float]] | None = None,
    ) -> KnowledgeGraph:
        del entities, embeddings  # structured graph uses classification only

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        signal_map = {s.name.lower(): s for s in signals}

        main_industry = self._main_industry_name(classification)
        main_industry_id = self._node_id(main_industry, "main_industry")
        primary = classification.primary_technology
        primary_id = self._node_id(primary, "main_industry_technology")

        nodes.append(GraphNode(
            id=main_industry_id,
            label=main_industry,
            node_type="main_industry",
            properties={
                "role": "main_industry",
                "is_center": True,
                "regulatory_domain": classification.regulatory_domain,
                "layer": 0,
            },
        ))

        primary_signal = signal_map.get(primary.lower())
        primary_conf = primary_signal.dvi.composite if primary_signal else 0.9

        nodes.append(GraphNode(
            id=primary_id,
            label=primary,
            node_type="main_industry_technology",
            properties={
                "role": "main_technology",
                "is_main": True,
                "signal_type": primary_signal.dvi.signal_type.value if primary_signal else "unknown",
                "confidence": primary_conf,
                "layer": 1,
            },
        ))
        edges.append(GraphEdge(
            source=main_industry_id,
            target=primary_id,
            relationship="central_to",
            probability=self._edge_prob(
                primary_conf, "influences", papers, main_industry, primary, signal_map,
            ),
            edge_class="main_tech",
        ))

        taxonomy_techs = self._taxonomy_techs(classification)
        blue_ids: list[str] = [primary_id]

        for sub in taxonomy_techs:
            if sub.name.lower() == primary.lower():
                continue
            tech_id = self._node_id(sub.name, "main_industry_technology")
            if any(n.id == tech_id for n in nodes):
                continue

            sig = signal_map.get(sub.name.lower())
            conf = sub.confidence if sub.confidence else (sig.dvi.composite if sig else 0.7)

            nodes.append(GraphNode(
                id=tech_id,
                label=sub.name,
                node_type="main_industry_technology",
                properties={
                    "role": "taxonomy_technology",
                    "relationship": sub.relationship,
                    "direction": sub.direction,
                    "confidence": conf,
                    "category": classification.primary_category,
                    "layer": 1,
                },
            ))
            blue_ids.append(tech_id)

            edges.append(GraphEdge(
                source=main_industry_id,
                target=tech_id,
                relationship=sub.relationship,
                probability=self._edge_prob(conf, sub.relationship, papers, main_industry, sub.name, signal_map),
                edge_class="main_tech",
            ))

            m_rel = sub.relationship
            if sub.direction == "affects_main":
                edges.append(GraphEdge(
                    source=tech_id,
                    target=primary_id,
                    relationship=m_rel,
                    probability=self._edge_prob(conf, m_rel, papers, sub.name, primary, signal_map),
                    edge_class="tech_to_main",
                ))
            elif sub.direction == "affected_by_main":
                edges.append(GraphEdge(
                    source=primary_id,
                    target=tech_id,
                    relationship=m_rel,
                    probability=self._edge_prob(conf, m_rel, papers, primary, sub.name, signal_map),
                    edge_class="tech_to_main",
                ))
            elif sub.direction == "bidirectional":
                edges.append(GraphEdge(
                    source=tech_id,
                    target=primary_id,
                    relationship=m_rel,
                    probability=self._edge_prob(conf, m_rel, papers, sub.name, primary, signal_map),
                    edge_class="tech_to_main",
                ))

        industry_tech_map = self._industry_tech_map(classification)
        related_names = self._related_industry_names(classification, main_industry)

        if not related_names and industry_tech_map:
            related_names = list(industry_tech_map.keys())

        # Guarantee exactly one main_industry node — no related industry duplicates it
        related_names = [
            n for n in related_names
            if n.lower() != main_industry.lower()
        ]

        for idx, ind_name in enumerate(related_names):
            ind_id = self._node_id(ind_name, "related_industry")
            if any(n.id == ind_id for n in nodes):
                continue

            ind_conf = 0.75
            for aff in classification.affected_industries:
                if aff.name.lower() == ind_name.lower():
                    ind_conf = aff.confidence
                    break

            nodes.append(GraphNode(
                id=ind_id,
                label=ind_name,
                node_type="related_industry",
                properties={
                    "role": "related_industry",
                    "confidence": ind_conf,
                    "layer": 2,
                    "ring_index": idx,
                },
            ))
            edges.append(GraphEdge(
                source=main_industry_id,
                target=ind_id,
                relationship="influences",
                probability=self._edge_prob(ind_conf, "influences", papers, main_industry, ind_name, signal_map),
                edge_class="industry",
            ))

            techs = industry_tech_map.get(ind_name, [])
            if not techs:
                for aff in classification.affected_industries:
                    if aff.name.lower() == ind_name.lower():
                        techs = aff.technologies
                        break

            for t_idx, tech in enumerate(techs):
                tech_id = self._node_id(f"{ind_name}:{tech.name}", "industry_technology")
                if any(n.id == tech_id for n in nodes):
                    continue

                sig = signal_map.get(tech.name.lower())
                conf = tech.confidence if tech.confidence else (sig.dvi.composite if sig else 0.65)

                nodes.append(GraphNode(
                    id=tech_id,
                    label=tech.name,
                    node_type="industry_technology",
                    properties={
                        "role": "industry_technology",
                        "parent_industry": ind_name,
                        "parent_industry_id": ind_id,
                        "relationship": tech.relationship,
                        "direction": tech.direction,
                        "confidence": conf,
                        "layer": 3,
                        "ring_index": t_idx,
                    },
                ))
                edges.append(GraphEdge(
                    source=ind_id,
                    target=tech_id,
                    relationship=tech.relationship,
                    probability=self._edge_prob(conf, tech.relationship, papers, ind_name, tech.name, signal_map),
                    edge_class="industry_tech",
                ))

                if tech.direction == "affects_main":
                    edges.append(GraphEdge(
                        source=tech_id,
                        target=primary_id,
                        relationship=tech.relationship,
                        probability=self._edge_prob(conf, tech.relationship, papers, tech.name, primary, signal_map),
                        edge_class="cross_link",
                    ))
                elif tech.direction == "affected_by_main":
                    edges.append(GraphEdge(
                        source=primary_id,
                        target=tech_id,
                        relationship=tech.relationship,
                        probability=self._edge_prob(conf, tech.relationship, papers, primary, tech.name, signal_map),
                        edge_class="cross_link",
                    ))
                elif tech.direction == "bidirectional":
                    edges.append(GraphEdge(
                        source=tech_id,
                        target=primary_id,
                        relationship=tech.relationship,
                        probability=self._edge_prob(conf * 0.85, tech.relationship, papers, tech.name, primary, signal_map),
                        edge_class="cross_link",
                    ))

        return KnowledgeGraph(
            nodes=nodes,
            edges=edges,
            main_technology_id=primary_id,
            main_technology_label=primary,
            main_industry_id=main_industry_id,
            main_industry_label=main_industry,
            propagation_paths=[],
        )
