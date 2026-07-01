"""
Impact tree: emerging technologies → combinations → DVI evolution speed
→ year-by-year milestones → final M state (scenario seeds).
"""
import math
from itertools import combinations

from tdi.models.schemas import (
    ClassificationResult,
    ImpactTreeNode,
    KnowledgeGraph,
    TechnologySignal,
)

BASE_YEAR = 2026
MAX_COMBO_PATHS = 16
MIN_COMBO_RELATION_PROB = 0.28

SPEED_CLUSTER = {
    "rapid": "disruptive",
    "accelerated": "converged",
    "gradual": "emerging_opportunity",
    "latent": "uncertain",
}

SPEED_LABELS = {
    "rapid": "Rapid Tech Evolution",
    "accelerated": "Accelerated Tech Evolution",
    "gradual": "Gradual Tech Evolution",
    "latent": "Latent Tech Evolution",
}

YEARLY_STEPS = {
    "rapid": 5,
    "accelerated": 4,
    "gradual": 3,
    "latent": 2,
}

# Technology-evolution phases only (no market adoption / acceptability)
PHASE_LABELS = [
    "Early R&D signals — {combo} capability research begins affecting {primary}",
    "Prototype emergence — experimental {combo} subsystems appear",
    "Architecture fusion — {primary} stack integrates {combo} components",
    "Capability convergence — {combo} co-design reshapes {primary} core functions",
    "Mature evolution — {primary} reaches next-generation architecture with {combo}",
]


class ImpactTreeBuilder:
    def _node_label_map(self, knowledge_graph: KnowledgeGraph) -> dict[str, str]:
        return {n.label.lower(): n.id for n in knowledge_graph.nodes}

    def _edge_probability_between(
        self, id_a: str, id_b: str, knowledge_graph: KnowledgeGraph,
    ) -> float:
        if not id_a or not id_b:
            return 0.0
        best = 0.0
        for edge in knowledge_graph.edges:
            if (edge.source == id_a and edge.target == id_b) or (
                edge.source == id_b and edge.target == id_a
            ):
                best = max(best, edge.probability)
        return best

    def _tech_main_probability(
        self, tech_name: str, primary: str, knowledge_graph: KnowledgeGraph,
    ) -> float:
        label_map = self._node_label_map(knowledge_graph)
        primary_id = knowledge_graph.main_technology_id or label_map.get(primary.lower(), "")
        tech_id = label_map.get(tech_name.lower(), "")
        return self._edge_probability_between(tech_id, primary_id, knowledge_graph)

    def _group_relation_score(
        self,
        signals: list[TechnologySignal],
        primary: str,
        knowledge_graph: KnowledgeGraph,
    ) -> float:
        """Combined KG relation score for a technology group (main links + cross-links)."""
        if not signals:
            return 0.0

        label_map = self._node_label_map(knowledge_graph)
        main_probs = [
            self._tech_main_probability(s.name, primary, knowledge_graph)
            for s in signals
        ]
        base = sum(main_probs) / len(main_probs)

        if len(signals) == 1:
            return round(base, 3)

        tech_ids = [label_map.get(s.name.lower(), "") for s in signals]
        cross_probs: list[float] = []
        for i in range(len(tech_ids)):
            for j in range(i + 1, len(tech_ids)):
                cross_probs.append(
                    self._edge_probability_between(tech_ids[i], tech_ids[j], knowledge_graph),
                )

        cross_avg = sum(cross_probs) / len(cross_probs) if cross_probs else 0.0
        synergy = min(0.12, 0.04 * (len(signals) - 1))
        score = 0.58 * base + 0.32 * cross_avg + synergy
        return round(min(max(score, 0.0), 1.0), 3)

    def _signal_map(self, signals: list[TechnologySignal]) -> dict[str, TechnologySignal]:
        return {s.name.lower(): s for s in signals}

    def _relationship_to_main(
        self,
        tech_name: str,
        primary: str,
        knowledge_graph: KnowledgeGraph,
        classification: ClassificationResult,
    ) -> str:
        primary_id = knowledge_graph.main_technology_id
        tech_node = next(
            (n for n in knowledge_graph.nodes if n.label.lower() == tech_name.lower()),
            None,
        )
        if tech_node and primary_id:
            for edge in knowledge_graph.edges:
                if edge.edge_class in ("tech_to_main", "cross_link"):
                    if edge.source == tech_node.id and edge.target == primary_id:
                        return edge.relationship
                    if edge.target == tech_node.id and edge.source == primary_id:
                        return f"affected_by_{edge.relationship}"

        for cat in classification.technology_categories:
            for sub in cat.subcategories:
                if sub.name.lower() == tech_name.lower():
                    return sub.relationship

        for ind in classification.affected_industries:
            for tech in ind.technologies:
                if tech.name.lower() == tech_name.lower():
                    return tech.relationship

        for tech in classification.main_industry_technologies:
            if tech.name.lower() == tech_name.lower():
                return tech.relationship

        return "influences"

    def _edge_effect(
        self,
        tech_name: str,
        primary: str,
        knowledge_graph: KnowledgeGraph,
        signal: TechnologySignal,
    ) -> float:
        tech_node = next(
            (n for n in knowledge_graph.nodes if n.label.lower() == tech_name.lower()),
            None,
        )
        primary_id = knowledge_graph.main_technology_id
        if tech_node and primary_id:
            for edge in knowledge_graph.edges:
                if edge.edge_class in ("tech_to_main", "cross_link", "industry_tech"):
                    if tech_node.id in (edge.source, edge.target) and primary_id in (edge.source, edge.target):
                        return round(edge.probability * signal.dvi.impact, 3)
        return round(signal.dvi.impact * 0.65, 3)

    def _compute_speed(
        self,
        signals: list[TechnologySignal],
    ) -> tuple[str, float]:
        if not signals:
            return "gradual", 0.35

        composites = [s.dvi.composite for s in signals]
        growths = [
            float(s.formula_metrics.get("growth_rate", s.dvi.composite))
            for s in signals
        ]
        diffusions = [s.dvi.diffusion for s in signals]

        composite = sum(composites) / len(composites)
        growth = max(growths)
        diffusion = sum(diffusions) / len(diffusions)

        # Synergy: more technologies → slightly faster combined evolution
        synergy = min(0.12, 0.04 * (len(signals) - 1))
        speed_score = round(
            0.38 * composite + 0.34 * growth + 0.28 * diffusion + synergy,
            3,
        )

        if speed_score >= 0.62:
            return "rapid", speed_score
        if speed_score >= 0.42:
            return "accelerated", speed_score
        if speed_score >= 0.22:
            return "gradual", speed_score
        return "latent", speed_score

    def _combined_impact(self, signals: list[TechnologySignal], knowledge_graph: KnowledgeGraph, primary: str) -> float:
        if not signals:
            return 0.3
        effects = [
            self._edge_effect(s.name, primary, knowledge_graph, s)
            for s in signals
        ]
        combined = 1.0
        for e in effects:
            combined *= 1.0 - min(e, 0.95)
        return round(1.0 - combined, 3)

    def _outcome_label(
        self,
        primary: str,
        tech_names: list[str],
        speed: str,
        target_year: int,
    ) -> str:
        combo = " + ".join(tech_names[:3])
        if len(tech_names) > 3:
            combo += f" +{len(tech_names) - 3} more"

        templates = {
            "rapid": f"{primary} → Next-gen architecture fusing {combo} by {target_year}",
            "accelerated": f"{primary} → Advanced stack converging {combo} capabilities by {target_year}",
            "gradual": f"{primary} → Incremental technical evolution via {combo} by {target_year}",
            "latent": f"{primary} → Early-stage R&D pathway with {combo} by {target_year}",
        }
        return templates.get(speed, f"{primary} → Evolved state with {combo} by {target_year}")

    def _evolution_years(self, target_year: int, speed: str) -> list[int]:
        span = target_year - BASE_YEAR
        if span <= 1:
            return []

        n_steps = min(YEARLY_STEPS.get(speed, 3), span - 1)
        years: list[int] = []
        for i in range(1, n_steps + 1):
            y = BASE_YEAR + round(span * i / (n_steps + 1))
            if BASE_YEAR < y < target_year:
                years.append(y)
        return sorted(set(years))

    def _technical_evolution_pct(self, year: int, target_year: int, speed_score: float) -> float:
        """Technical evolution progress along the forecast horizon (0–1)."""
        span = max(target_year - BASE_YEAR, 1)
        t = (year - BASE_YEAR) / span
        k = 3.2 + speed_score * 7.0
        progress = 1.0 / (1.0 + math.exp(-k * (t - 0.42)))
        return round(min(max(progress, 0.05), 0.98), 3)

    def _milestone_label(
        self,
        primary: str,
        tech_names: list[str],
        year: int,
        maturity: float,
    ) -> str:
        combo = " + ".join(tech_names[:2])
        if len(tech_names) > 2:
            combo += f" (+{len(tech_names) - 2})"
        phase_idx = min(int(maturity * len(PHASE_LABELS)), len(PHASE_LABELS) - 1)
        phase = PHASE_LABELS[phase_idx].format(combo=combo, primary=primary)
        return f"{year}: {phase}"

    def _speed_score_signal(self, signal: TechnologySignal) -> float:
        growth = float(signal.formula_metrics.get("growth_rate", signal.dvi.composite))
        return round(
            0.38 * signal.dvi.composite + 0.34 * growth + 0.28 * signal.dvi.diffusion,
            3,
        )

    def _peak_effect_year_for_signal(
        self,
        signal: TechnologySignal,
        target_year: int,
        rank_idx: int = 0,
        total: int = 1,
    ) -> int:
        """Year when this technology's effect on M is strongest."""
        growth = float(signal.formula_metrics.get("growth_rate", signal.dvi.composite))
        composite = signal.dvi.composite
        diffusion = signal.dvi.diffusion
        rank_shift = (rank_idx / max(total - 1, 1)) * 0.28 if total > 1 else 0.0
        name_var = (sum(ord(c) for c in signal.name) % 9 - 4) * 0.025
        peak_fraction = (
            0.18 + (1.0 - growth) * 0.32 + (1.0 - composite) * 0.22
            + (1.0 - diffusion) * 0.12 - rank_shift + name_var
        )
        peak_fraction = max(0.08, min(0.85, peak_fraction))
        span = max(target_year - BASE_YEAR, 1)
        year = BASE_YEAR + max(1, round(span * peak_fraction))
        if year >= target_year:
            year = target_year - 1
        return max(BASE_YEAR + 1, year)

    def _peak_effect_year_for_combo(
        self,
        signals: list[TechnologySignal],
        target_year: int,
        speed_score: float,
        knowledge_graph: KnowledgeGraph,
        primary: str,
    ) -> int:
        if not signals:
            return BASE_YEAR + 1
        member_peaks = [
            self._peak_effect_year_for_signal(s, target_year, i, len(signals))
            for i, s in enumerate(signals)
        ]
        # Combination peaks when combined influence is highest — after last member emerges
        combo_peak = max(member_peaks)
        if len(signals) > 1:
            avg_peak = sum(member_peaks) / len(signals)
            combo_peak = round(avg_peak * 0.4 + combo_peak * 0.6)
        combo_peak = min(combo_peak, target_year - 1)
        return max(BASE_YEAR + 1, combo_peak)

    def _velocity_peak_year(
        self, combo_peak: int, target_year: int, speed: str,
    ) -> int:
        span = max(target_year - combo_peak, 1)
        offset = {"rapid": 1, "accelerated": 2, "gradual": 3, "latent": 4}.get(speed, 2)
        return min(combo_peak + offset, target_year - 1)

    def _build_yearly_chain(
        self,
        combo_id: str,
        primary: str,
        tech_names: list[str],
        target_year: int,
        speed: str,
        speed_score: float,
        avg_composite: float,
        avg_growth: float,
        combined_impact: float,
        rel_summary: str,
        outcome: ImpactTreeNode,
    ) -> ImpactTreeNode:
        years = self._evolution_years(target_year, speed)
        if not years:
            return outcome

        chain: ImpactTreeNode = outcome
        for year in reversed(years):
            maturity = self._technical_evolution_pct(year, target_year, speed_score)
            impact_at_year = round(combined_impact * maturity, 3)
            milestone = ImpactTreeNode(
                id=f"{combo_id}-year-{year}",
                label=self._milestone_label(primary, tech_names, year, maturity),
                node_type="evolution_milestone",
                impact_score=impact_at_year,
                dvi_composite=round(avg_composite * maturity, 3),
                growth_rate=avg_growth,
                evolution_speed=speed,
                evolution_year=year,
                maturity_pct=maturity,
                target_year=target_year,
                contributing_technologies=tech_names,
                relationship_to_main=rel_summary,
                path_id=combo_id,
                children=[chain],
            )
            chain = milestone
        return chain

    def _build_combination_path(
        self,
        combo_signals: list[TechnologySignal],
        primary: str,
        target_year: int,
        knowledge_graph: KnowledgeGraph,
        classification: ClassificationResult,
        path_idx: int,
        relation_probability: float = 0.0,
    ) -> ImpactTreeNode:
        tech_names = [s.name for s in combo_signals]
        speed, speed_score = self._compute_speed(combo_signals)
        combined_impact = self._combined_impact(combo_signals, knowledge_graph, primary)
        relationships = [
            self._relationship_to_main(s.name, primary, knowledge_graph, classification)
            for s in combo_signals
        ]
        rel_summary = ", ".join(dict.fromkeys(relationships))

        combo_label = " + ".join(tech_names) if len(tech_names) > 1 else tech_names[0]
        combo_id = f"combo-{path_idx}-{'-'.join(t[:8] for t in tech_names)}"

        avg_composite = round(
            sum(s.dvi.composite for s in combo_signals) / len(combo_signals), 3,
        )
        avg_growth = round(
            sum(
                float(s.formula_metrics.get("growth_rate", s.dvi.composite))
                for s in combo_signals
            ) / len(combo_signals),
            3,
        )

        combo_peak = self._peak_effect_year_for_combo(
            combo_signals, target_year, speed_score, knowledge_graph, primary,
        )
        vel_peak = self._velocity_peak_year(combo_peak, target_year, speed)

        outcome = ImpactTreeNode(
            id=f"{combo_id}-outcome",
            label=self._outcome_label(primary, tech_names, speed, target_year),
            node_type="evolved_outcome",
            impact_score=combined_impact,
            dvi_composite=avg_composite,
            growth_rate=avg_growth,
            evolution_speed=speed,
            evolution_year=target_year,
            maturity_pct=1.0,
            target_year=target_year,
            contributing_technologies=tech_names,
            relationship_to_main=rel_summary,
            scenario_cluster_hint=SPEED_CLUSTER[speed],
            is_scenario_seed=True,
            path_id=combo_id,
            children=[],
        )

        yearly_head = self._build_yearly_chain(
            combo_id, primary, tech_names, target_year, speed, speed_score,
            avg_composite, avg_growth, combined_impact, rel_summary, outcome,
        )

        year_count = len(self._evolution_years(target_year, speed))
        velocity = ImpactTreeNode(
            id=f"{combo_id}-velocity",
            label=f"{SPEED_LABELS[speed]} · {year_count} steps to {target_year}",
            node_type="evolution_velocity",
            impact_score=speed_score,
            dvi_composite=avg_composite,
            growth_rate=avg_growth,
            evolution_speed=speed,
            evolution_year=vel_peak,
            peak_effect_year=vel_peak,
            target_year=target_year,
            contributing_technologies=tech_names,
            path_id=combo_id,
            children=[yearly_head],
        )

        return ImpactTreeNode(
            id=combo_id,
            label=f"Combination: {combo_label}",
            node_type="tech_combination",
            impact_score=combined_impact,
            dvi_composite=avg_composite,
            growth_rate=avg_growth,
            evolution_year=combo_peak,
            peak_effect_year=combo_peak,
            contributing_technologies=tech_names,
            relationship_to_main=rel_summary,
            relation_probability=relation_probability,
            path_id=combo_id,
            children=[velocity],
        )

    def _emerging_signals(
        self,
        primary: str,
        signals: list[TechnologySignal],
    ) -> list[TechnologySignal]:
        emerging = [
            s for s in signals
            if s.name.lower() != primary.lower()
        ]
        emerging.sort(key=lambda s: s.dvi.composite, reverse=True)
        return emerging[:12]

    def _build_combinations(
        self,
        emerging: list[TechnologySignal],
        primary: str,
        knowledge_graph: KnowledgeGraph,
    ) -> list[tuple[list[TechnologySignal], float]]:
        """Build combination paths ranked by knowledge-graph relation probability."""
        if not emerging:
            return []

        ranked = sorted(
            emerging,
            key=lambda s: (
                self._tech_main_probability(s.name, primary, knowledge_graph) * 0.65
                + s.dvi.composite * 0.35
            ),
            reverse=True,
        )
        pool = ranked[:10]
        candidates: list[tuple[list[TechnologySignal], float]] = []
        seen: set[tuple[str, ...]] = set()

        def add(group: list[TechnologySignal]) -> None:
            key = tuple(sorted(s.name.lower() for s in group))
            if not key or key in seen:
                return
            score = self._group_relation_score(group, primary, knowledge_graph)
            min_score = MIN_COMBO_RELATION_PROB if len(group) == 1 else MIN_COMBO_RELATION_PROB * 0.82
            if score < min_score:
                return
            seen.add(key)
            candidates.append((group, score))

        for signal in pool:
            add([signal])

        for pair in combinations(pool, 2):
            add(list(pair))

        for triple in combinations(pool[:8], 3):
            add(list(triple))

        for quad in combinations(pool[:6], 4):
            add(list(quad))

        if len(pool) >= 4:
            add(pool[:4])

        pool_names = {s.name.lower() for s in pool}
        for path in knowledge_graph.propagation_paths[:12]:
            matched = [
                s for s in pool
                if s.name.lower() in {lbl.lower() for lbl in path.path_labels}
                and s.name.lower() in pool_names
            ]
            if len(matched) >= 2:
                add(matched[:2])
            if len(matched) >= 3:
                add(matched[:3])

        candidates.sort(key=lambda item: item[1], reverse=True)

        deduped: list[tuple[list[TechnologySignal], float]] = []
        used_keys: set[tuple[str, ...]] = set()
        for group, score in candidates:
            key = tuple(sorted(s.name.lower() for s in group))
            if key not in used_keys:
                used_keys.add(key)
                deduped.append((group, score))

        return deduped[:MAX_COMBO_PATHS]

    def build(
        self,
        classification: ClassificationResult,
        signals: list[TechnologySignal],
        knowledge_graph: KnowledgeGraph,
        target_year: int = 2035,
    ) -> ImpactTreeNode:
        primary = classification.primary_technology
        primary_signal = next(
            (s for s in signals if s.name.lower() == primary.lower()),
            signals[0] if signals else None,
        )
        primary_dvi = primary_signal.dvi.composite if primary_signal else 0.5
        primary_growth = (
            float(primary_signal.formula_metrics.get("growth_rate", primary_dvi))
            if primary_signal else 0.3
        )

        emerging = self._emerging_signals(primary, signals)
        combo_paths = self._build_combinations(emerging, primary, knowledge_graph)

        emerging_children = []
        for i, signal in enumerate(emerging):
            rel = self._relationship_to_main(
                signal.name, primary, knowledge_graph, classification,
            )
            effect = self._edge_effect(signal.name, primary, knowledge_graph, signal)
            growth = float(signal.formula_metrics.get("growth_rate", signal.dvi.composite))
            peak_year = self._peak_effect_year_for_signal(signal, target_year, i, len(emerging))
            emerging_children.append(ImpactTreeNode(
                id=f"emerge-{i}-{signal.name[:20]}",
                label=signal.name,
                node_type="emerging_technology",
                impact_score=effect,
                dvi_composite=signal.dvi.composite,
                growth_rate=growth,
                evolution_year=peak_year,
                peak_effect_year=peak_year,
                target_year=target_year,
                relationship_to_main=rel,
                contributing_technologies=[signal.name],
                children=[],
            ))

        combination_children = [
            self._build_combination_path(
                combo, primary, target_year, knowledge_graph, classification, i,
                relation_probability=rel_prob,
            )
            for i, (combo, rel_prob) in enumerate(combo_paths)
        ]

        return ImpactTreeNode(
            id="root-main-technology",
            label=primary,
            node_type="main_technology",
            impact_score=primary_signal.dvi.impact if primary_signal else 0.5,
            dvi_composite=primary_dvi,
            growth_rate=primary_growth,
            target_year=target_year,
            contributing_technologies=[primary],
            children=[
                ImpactTreeNode(
                    id="branch-emerging",
                    label=f"Emerging Technologies affecting {primary}",
                    node_type="branch",
                    impact_score=round(
                        sum(c.impact_score for c in emerging_children) / max(len(emerging_children), 1),
                        3,
                    ) if emerging_children else 0.3,
                    children=emerging_children,
                ),
                ImpactTreeNode(
                    id="branch-combinations",
                    label=f"Technology Combinations → Evolution by {target_year}",
                    node_type="branch",
                    impact_score=round(
                        sum(c.impact_score for c in combination_children) / max(len(combination_children), 1),
                        3,
                    ) if combination_children else 0.3,
                    target_year=target_year,
                    children=combination_children,
                ),
            ],
        )

    @staticmethod
    def extract_scenario_seeds(tree: ImpactTreeNode) -> list[ImpactTreeNode]:
        seeds: list[ImpactTreeNode] = []

        def walk(node: ImpactTreeNode) -> None:
            if node.is_scenario_seed:
                seeds.append(node)
            for child in node.children:
                walk(child)

        walk(tree)
        return seeds
