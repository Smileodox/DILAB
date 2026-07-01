import uuid
from tdi.models.schemas import (
    ClassificationResult,
    FutureScenario,
    ImpactTreeNode,
    ScenarioCluster,
    TechnologySignal,
    ArxivPaper,
)
from tdi.services.impact_tree import ImpactTreeBuilder
from tdi.services.ml_probability import (
    assign_scenario_clusters_ml,
    confidence_ml,
    scenario_probabilities_ml,
)


class ScenarioGenerator:
    SPEED_SCORE = {
        "rapid": 0.92,
        "accelerated": 0.72,
        "gradual": 0.48,
        "latent": 0.22,
    }

    SCENARIO_TEMPLATES = [
        {
            "suffix": "Technology Convergence",
            "cluster": ScenarioCluster.MAINSTREAM,
            "visibility_range": (0.5, 0.8),
            "impact_range": (0.4, 0.7),
        },
        {
            "suffix": "Disruptive Tech Breakthrough",
            "cluster": ScenarioCluster.DISRUPTIVE,
            "visibility_range": (0.3, 0.6),
            "impact_range": (0.7, 0.95),
        },
        {
            "suffix": "Emerging Tech Pathway",
            "cluster": ScenarioCluster.EMERGING,
            "visibility_range": (0.2, 0.5),
            "impact_range": (0.5, 0.8),
        },
        {
            "suffix": "Uncertain Tech Trajectory",
            "cluster": ScenarioCluster.UNCERTAIN,
            "visibility_range": (0.1, 0.4),
            "impact_range": (0.3, 0.6),
        },
        {
            "suffix": "Accelerated Stack Integration",
            "cluster": ScenarioCluster.MAINSTREAM,
            "visibility_range": (0.6, 0.9),
            "impact_range": (0.5, 0.75),
        },
        {
            "suffix": "Latent Tech Disruption",
            "cluster": ScenarioCluster.DISRUPTIVE,
            "visibility_range": (0.1, 0.35),
            "impact_range": (0.6, 0.9),
        },
    ]

    CLUSTER_ENCODING = {
        ScenarioCluster.MAINSTREAM: 0.8,
        ScenarioCluster.DISRUPTIVE: 0.6,
        ScenarioCluster.EMERGING: 0.5,
        ScenarioCluster.UNCERTAIN: 0.3,
    }

    def _speed_score(self, speed: str) -> float:
        return self.SPEED_SCORE.get(speed, 0.48)

    def _cluster_from_label(self, label: str) -> ScenarioCluster:
        mapping = {
            "mainstream": ScenarioCluster.MAINSTREAM,
            "disruptive": ScenarioCluster.DISRUPTIVE,
            "emerging_opportunity": ScenarioCluster.EMERGING,
            "uncertain": ScenarioCluster.UNCERTAIN,
        }
        return mapping.get(label, ScenarioCluster.EMERGING)

    def generate(
        self,
        classification: ClassificationResult,
        signals: list[TechnologySignal],
        papers: list[ArxivPaper],
        target_year: int,
        impact_tree: ImpactTreeNode | None = None,
    ) -> list[FutureScenario]:
        seeds = ImpactTreeBuilder.extract_scenario_seeds(impact_tree) if impact_tree else []
        if seeds:
            return self._generate_from_impact_tree(
                classification, signals, papers, target_year, seeds,
            )
        return self._generate_from_templates(classification, signals, papers, target_year)

    def _generate_from_impact_tree(
        self,
        classification: ClassificationResult,
        signals: list[TechnologySignal],
        papers: list[ArxivPaper],
        target_year: int,
        seeds: list[ImpactTreeNode],
    ) -> list[FutureScenario]:
        years_ahead = target_year - 2026
        signal_map = {s.name.lower(): s for s in signals}
        cluster_features: list[list[float]] = []
        prob_features: list[list[float]] = []
        draft: list[dict] = []

        for seed in seeds:
            tech_names = seed.contributing_technologies or [classification.primary_technology]
            primary_tech = tech_names[0]
            matched_signals = [
                signal_map[t.lower()]
                for t in tech_names
                if t.lower() in signal_map
            ]
            anchor = matched_signals[0] if matched_signals else None
            speed = seed.evolution_speed or "gradual"

            vis = seed.dvi_composite if seed.dvi_composite is not None else (
                anchor.dvi.visibility if anchor else 0.4
            )
            imp = seed.impact_score if seed.impact_score else (
                anchor.dvi.impact if anchor else 0.5
            )
            dvi_composite = seed.dvi_composite if seed.dvi_composite is not None else (
                anchor.dvi.composite if anchor else 0.35
            )
            growth = seed.growth_rate if seed.growth_rate is not None else (
                float(anchor.formula_metrics.get("growth_rate", dvi_composite)) if anchor else 0.3
            )
            speed_score = self._speed_score(speed)

            cluster_features.append([vis, imp, dvi_composite, growth, speed_score])
            prob_features.append([vis, imp, dvi_composite, growth])

            draft.append({
                "seed": seed,
                "tech_name": primary_tech,
                "tech_names": tech_names,
                "signal": anchor,
                "vis": vis,
                "imp": imp,
                "dvi_composite": dvi_composite,
                "speed": speed,
            })

        ml_clusters = assign_scenario_clusters_ml(cluster_features)
        ml_probs = scenario_probabilities_ml(prob_features)
        scenarios: list[FutureScenario] = []

        for item, cluster_label, prob in zip(draft, ml_clusters, ml_probs):
            seed = item["seed"]
            tech_name = item["tech_name"]
            tech_names = item["tech_names"]
            cluster = self._cluster_from_label(cluster_label)
            signal = item["signal"]
            speed = item["speed"]

            confidence = confidence_ml(
                item["dvi_composite"],
                paper_count=sum(
                    1 for p in papers
                    if any(t.lower() in (p.title + p.abstract).lower() for t in tech_names)
                ),
                entity_count=len(tech_names),
            )

            scenarios.append(FutureScenario(
                id=str(uuid.uuid4())[:8],
                title=seed.label,
                description=self._build_seed_description(
                    classification, target_year, years_ahead, tech_names, speed, signal, seed,
                ),
                cluster=cluster,
                probability=prob,
                confidence=confidence,
                visibility_degree=item["vis"],
                impact_degree=item["imp"],
                risks=self._generate_tech_evolution_risks(tech_names, speed, classification),
                opportunities=self._generate_tech_evolution_opportunities(tech_names, speed, classification),
                supporting_evidence=self._gather_evidence(tech_name, papers),
                regulatory_impacts=self._generate_tech_evolution_dependencies(
                    tech_names, classification, target_year,
                ),
                technological_dependencies=tech_names[1:] if len(tech_names) > 1 else self._generate_dependencies(tech_name, signals),
            ))

        return sorted(
            scenarios,
            key=lambda s: (s.cluster.value, -s.probability),
        )

    def _build_seed_description(
        self,
        classification: ClassificationResult,
        target_year: int,
        years_ahead: int,
        tech_names: list[str],
        speed: str,
        signal: TechnologySignal | None,
        seed: ImpactTreeNode,
    ) -> str:
        combo = ", ".join(tech_names)
        speed_desc = {
            "rapid": "rapid architectural convergence driven by strong DVI evolution signals",
            "accelerated": "accelerated co-evolution of combined technology capabilities",
            "gradual": "gradual incremental technical evolution across the stack",
            "latent": "latent R&D pathway with weak early technical signals",
        }
        signal_info = ""
        if signal:
            signal_info = (
                f" DVI composite {signal.dvi.composite:.2f}, "
                f"ML growth rate {float(signal.formula_metrics.get('growth_rate', signal.dvi.composite)):.2f}."
            )

        return (
            f"Technology evolution outcome for {classification.primary_technology}: "
            f"when {combo} combine technically ({seed.relationship_to_main}), "
            f"{speed_desc.get(speed, 'evolution')} projects the main technology architecture "
            f"to reach this evolved state by {target_year} ({years_ahead} years)."
            f"{signal_info}"
        )

    def _generate_from_templates(
        self,
        classification: ClassificationResult,
        signals: list[TechnologySignal],
        papers: list[ArxivPaper],
        target_year: int,
    ) -> list[FutureScenario]:
        scenarios = []
        years_ahead = target_year - 2026
        cluster_features: list[list[float]] = []
        prob_features: list[list[float]] = []
        draft: list[dict] = []

        for i, template in enumerate(self.SCENARIO_TEMPLATES):
            signal = signals[i % len(signals)] if signals else None
            tech_name = signal.name if signal else classification.primary_technology

            vis = self._interpolate(template["visibility_range"], signal)
            imp = self._interpolate(template["impact_range"], signal)
            dvi_composite = signal.dvi.composite if signal else 0.3
            growth = float(signal.formula_metrics.get("growth_rate", dvi_composite)) if signal else 0.3
            speed_score = self.CLUSTER_ENCODING[template["cluster"]]

            cluster_features.append([vis, imp, dvi_composite, growth, speed_score])
            prob_features.append([vis, imp, dvi_composite, growth])

            draft.append({
                "tech_name": tech_name,
                "template": template,
                "signal": signal,
                "vis": vis,
                "imp": imp,
                "dvi_composite": dvi_composite,
            })

        ml_clusters = assign_scenario_clusters_ml(cluster_features)
        ml_probs = scenario_probabilities_ml(prob_features)

        for item, cluster_label, prob in zip(draft, ml_clusters, ml_probs):
            signal = item["signal"]
            template = item["template"]
            tech_name = item["tech_name"]
            cluster = self._cluster_from_label(cluster_label)

            confidence = confidence_ml(
                item["dvi_composite"],
                paper_count=sum(1 for p in papers if tech_name.lower() in (p.title + p.abstract).lower()),
                entity_count=3,
            )

            scenarios.append(FutureScenario(
                id=str(uuid.uuid4())[:8],
                title=f"{tech_name} — {template['suffix']} by {target_year}",
                description=self._build_description(
                    tech_name, template, classification, target_year, years_ahead, signal
                ),
                cluster=cluster,
                probability=prob,
                confidence=confidence,
                visibility_degree=item["vis"],
                impact_degree=item["imp"],
                risks=self._generate_risks(tech_name, cluster, classification),
                opportunities=self._generate_opportunities(tech_name, cluster, classification),
                supporting_evidence=self._gather_evidence(tech_name, papers),
                regulatory_impacts=self._generate_regulatory_impacts(
                    tech_name, classification, cluster, target_year
                ),
                technological_dependencies=self._generate_dependencies(tech_name, signals),
            ))

        return sorted(
            scenarios,
            key=lambda s: (s.cluster.value, -s.probability),
        )

    def _interpolate(self, range_tuple: tuple, signal: TechnologySignal | None) -> float:
        low, high = range_tuple
        if signal:
            mid = (low + high) / 2
            adjusted = mid + (signal.dvi.composite - 0.5) * (high - low) * 0.3
            return round(max(low, min(high, adjusted)), 3)
        return round((low + high) / 2, 3)

    def _build_description(
        self, tech, template, classification, target_year, years_ahead, signal
    ) -> str:
        cluster_desc = {
            ScenarioCluster.MAINSTREAM: "converged technology stack evolution with stable architectural integration",
            ScenarioCluster.DISRUPTIVE: "rapid disruptive technical breakthrough reshaping core capabilities",
            ScenarioCluster.EMERGING: "emerging technology pathway with evolving R&D and prototype stages",
            ScenarioCluster.UNCERTAIN: "high technical uncertainty with multiple competing evolution paths",
        }
        signal_info = ""
        if signal:
            signal_info = f" (DVI composite: {signal.dvi.composite}, signal: {signal.dvi.signal_type.value})"

        return (
            f"By {target_year} ({years_ahead} years ahead), {tech} drives "
            f"{cluster_desc[template['cluster']]} in {classification.regulatory_domain} "
            f"technology foresight{signal_info}."
        )

    def _generate_tech_evolution_risks(
        self, tech_names: list[str], speed: str, classification: ClassificationResult,
    ) -> list[str]:
        combo = " + ".join(tech_names[:3])
        base = [
            f"Interoperability gaps between {combo} and {classification.primary_technology}",
            f"Performance bottlenecks when fusing {combo} subsystems",
            "Immature interfaces between co-evolving technology layers",
        ]
        if speed in ("rapid", "accelerated"):
            base.append(f"Architecture instability from fast {combo} integration")
        if speed == "latent":
            base.append(f"Stalled R&D progress delaying {combo} technical maturation")
        return base[:4]

    def _generate_tech_evolution_opportunities(
        self, tech_names: list[str], speed: str, classification: ClassificationResult,
    ) -> list[str]:
        combo = " + ".join(tech_names[:3])
        base = [
            f"Next-generation capability uplift for {classification.primary_technology}",
            f"Cross-layer optimization from {combo} co-design",
            f"Novel functional primitives enabled by {combo}",
        ]
        if speed in ("rapid", "accelerated"):
            base.append(f"Breakthrough performance gains via {combo} fusion")
        return base[:4]

    def _generate_tech_evolution_dependencies(
        self, tech_names: list[str], classification: ClassificationResult, target_year: int,
    ) -> list[str]:
        primary = classification.primary_technology
        deps = [
            f"Core protocol evolution in {primary} by {target_year}",
            f"Subsystem interfaces between {primary} and {tech_names[0]}",
        ]
        if len(tech_names) > 1:
            deps.append(f"Cross-technology dependency chain: {' → '.join(tech_names[:3])}")
        deps.append("Compute and spectrum resource requirements for combined stack")
        return deps[:4]

    def _generate_risks(self, tech, cluster, classification) -> list[str]:
        base = [
            f"Regulatory lag behind {tech} deployment pace",
            f"Cross-border interference in {classification.regulatory_domain}",
            "Spectrum allocation conflicts with incumbent services",
        ]
        if cluster == ScenarioCluster.DISRUPTIVE:
            base.append(f"Market disruption from unregulated {tech} deployments")
        if cluster == ScenarioCluster.UNCERTAIN:
            base.append("Fragmented international regulatory harmonization")
        return base[:4]

    def _generate_opportunities(self, tech, cluster, classification) -> list[str]:
        industry = (
            classification.main_industry
            if classification.main_industry.strip()
            else (classification.related_industries[0] if classification.related_industries else "telecom")
        )
        base = [
            f"Enhanced spectrum efficiency through {tech}",
            "New revenue models for spectrum sharing",
            f"Improved service quality in {industry}",
        ]
        if cluster in (ScenarioCluster.EMERGING, ScenarioCluster.DISRUPTIVE):
            base.append(f"First-mover advantage in {tech} regulatory frameworks")
        return base[:4]

    def _gather_evidence(self, tech, papers) -> list[str]:
        evidence = []
        for paper in papers:
            if tech.lower() in (paper.title + paper.abstract).lower() or tech.lower() == paper.technology.lower():
                evidence.append(f"{paper.title} ({paper.published}) — arXiv:{paper.arxiv_id}")
        if not evidence and papers:
            evidence.append(f"{papers[0].title} ({papers[0].published}) — arXiv:{papers[0].arxiv_id}")
        return evidence[:3]

    def _generate_regulatory_impacts(self, tech, classification, cluster, target_year) -> list[str]:
        impacts = [
            f"Updated spectrum licensing rules for {tech} by {target_year}",
            f"Revised {classification.regulatory_domain} framework",
            "New technical conditions for equipment authorization",
        ]
        if cluster == ScenarioCluster.DISRUPTIVE:
            impacts.append(f"Emergency spectrum reallocation for {tech}")
        return impacts[:4]

    def _generate_dependencies(self, tech, signals) -> list[str]:
        deps = [s.name for s in signals if s.name != tech][:3]
        if not deps:
            deps = [s.name for s in signals[:3]]
        return deps
