from tdi.models.schemas import (
    ArxivPaper,
    DVIScores,
    ExtractedEntity,
    SignalType,
    TechnologySignal,
)
from tdi.services.ml_probability import estimate_growth_rates_ml
from tdi.services.yoon_formulas import TIME_WEIGHT, analyze_terms, classify_signal


class DVIAnalyzer:
    """
    DVI analyzer implementing Wang & Zhu (2026) MLWS-TF:
      - DoV / DoD / DoI quantification with time weighting (Yoon, 2012)
      - TF-IDF internal impact score for DoI (Eq. 11–13)
      - KVM / KDM / KIM quadrant maps with median thresholds
      - Three-dimensional joint validation for final signal classification
    """

    def analyze_all(
        self,
        technologies: list[str],
        papers: list[ArxivPaper],
        entities: list[ExtractedEntity],
        keywords: list[str],
    ) -> list[TechnologySignal]:
        terms = list(dict.fromkeys(technologies + keywords[:5]))
        raw_results, avg_tf, avg_df, growth_threshold, thresholds = analyze_terms(
            terms, papers, entities,
        )

        growth_map = estimate_growth_rates_ml({
            term: {
                "visibility": result.visibility,
                "diffusion": result.diffusion,
                "impact": result.impact,
                "absolute_tf": result.absolute_tf,
                "absolute_df": result.absolute_df,
                "avg_dov_rate": result.avg_dov_rate,
                "avg_dod_rate": result.avg_dod_rate,
                "avg_doi_rate": result.avg_doi_rate,
                "formula_growth": result.growth_rate,
                "period_count": len(result.periods),
            }
            for term, result in raw_results.items()
        })
        for term, ml_growth in growth_map.items():
            if term in raw_results:
                raw_results[term].growth_rate = ml_growth

        signals: list[TechnologySignal] = []
        for term in technologies:
            result = raw_results.get(term)
            if not result:
                result = raw_results.get(term.lower())  # type: ignore[assignment]

            if not result:
                signals.append(self._empty_signal(term))
                continue

            signal_type_str = classify_signal(result, avg_tf, avg_df, growth_threshold)
            signal_type = SignalType(signal_type_str)

            tech_keywords = [
                kw for kw in keywords
                if kw.lower() in term.lower() or term.lower() in kw.lower()
            ][:5]

            paper_count = sum(
                1 for p in papers
                if term.lower() in (p.title + p.abstract + p.technology).lower()
            )

            signals.append(
                TechnologySignal(
                    name=term,
                    dvi=DVIScores(
                        diffusion=result.diffusion,
                        visibility=result.visibility,
                        impact=result.impact,
                        composite=result.composite,
                        signal_type=signal_type,
                    ),
                    paper_count=paper_count,
                    keywords=tech_keywords,
                    formula_metrics={
                        "method": "Wang & Zhu (2026) MLWS-TF DVI",
                        "avg_dov": round(result.avg_dov, 6),
                        "avg_dov_rate": round(result.avg_dov_rate, 6),
                        "avg_dod": round(result.avg_dod, 6),
                        "avg_dod_rate": round(result.avg_dod_rate, 6),
                        "avg_doi": round(result.avg_doi, 6),
                        "avg_doi_rate": round(result.avg_doi_rate, 6),
                        "quadrant_visibility": result.quadrant_visibility,
                        "quadrant_diffusion": result.quadrant_diffusion,
                        "quadrant_impact": result.quadrant_impact,
                        "joint_consistent": result.joint_consistent,
                        "growth_rate": round(result.growth_rate, 4),
                        "growth_rate_method": "ML-GMM momentum (scikit-learn)",
                        "absolute_tf": round(result.absolute_tf, 3),
                        "absolute_df": round(result.absolute_df, 3),
                        "thresholds": {
                            "median_dov": round(thresholds.median_dov, 6),
                            "median_dov_rate": round(thresholds.median_dov_rate, 6),
                            "median_dod": round(thresholds.median_dod, 6),
                            "median_dod_rate": round(thresholds.median_dod_rate, 6),
                            "median_doi": round(thresholds.median_doi, 6),
                            "median_doi_rate": round(thresholds.median_doi_rate, 6),
                        },
                        "periods": [
                            {
                                "year": p.year,
                                "tf": p.tf,
                                "df": p.df,
                                "nn": p.nn,
                                "dov": round(p.dov, 4),
                                "dod": round(p.dod, 4),
                                "doi": round(p.doi, 4),
                                "dov_rate": round(p.dov_rate, 4),
                                "dod_rate": round(p.dod_rate, 4),
                                "doi_rate": round(p.doi_rate, 4),
                            }
                            for p in result.periods
                        ],
                        "formulas": {
                            "dov": "DoV(t) = (TF/|D(t)|) × (1 − α·(T−t))",
                            "dod": "DoD(t) = (DF/|D(t)|) × (1 − α·(T−t))",
                            "doi": "DoI(t) = (Σ I_i(d)/|D(t)|) × (1 − α·(T−t))",
                            "impact": "I_i(d) = TFIDF(k_i,d)/Σ_w TFIDF(w,d) if k_i ∈ d",
                            "rate": "DoX_rate(t) = (DoX(t) − DoX(t−1)) / DoX(t)",
                            "alpha": TIME_WEIGHT,
                            "classification": "Joint KVM + KDM + KIM quadrant agreement (median thresholds)",
                            "sources": [
                                "Wang & Zhu (2026) Expert Systems With Applications 298 — MLWS-TF",
                                "Yoon (2012) weak signal detection",
                            ],
                        },
                    },
                )
            )

        return sorted(signals, key=lambda s: s.dvi.composite, reverse=True)

    def _empty_signal(self, term: str) -> TechnologySignal:
        return TechnologySignal(
            name=term,
            dvi=DVIScores(
                diffusion=0.05,
                visibility=0.05,
                impact=0.05,
                composite=0.05,
                signal_type=SignalType.WEAK,
            ),
            paper_count=0,
            keywords=[],
            formula_metrics={"note": "Insufficient corpus data for term"},
        )
