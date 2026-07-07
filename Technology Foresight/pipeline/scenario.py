"""Uncertainty drivers, 2×2 scenario matrix, and technology impact trees."""
from __future__ import annotations

from typing import Any

from pipeline.reasoning import llm_chat
from pipeline.impact_paths import (
    build_tree_from_paths,
    discover_impact_paths,
    enrich_scenario_paths_with_llm,
    select_paths_for_scenario,
)

SCENARIO_TONES = {
    "optimistic": {"color": "#22C55E", "title": "Optimistic"},
    "disruptive": {"color": "#EF4444", "title": "Disruptive"},
    "constrained": {"color": "#F59E0B", "title": "Constrained"},
    "stagnant": {"color": "#6B7280", "title": "Stagnant"},
}


def extract_uncertainty_drivers(events: list[dict], clusters: list[dict]) -> list[dict]:
    drivers = []
    if events:
        emerge = [e for e in events if e.get("type") == "emerge"]
        die = [e for e in events if e.get("type") == "die"]
        if emerge:
            drivers.append(
                {
                    "axis": "Adoption velocity",
                    "description": (
                        f"{len(emerge)} emerging topic(s) create uncertainty about which "
                        "technology will cross the chasm first."
                    ),
                    "why": "Derived from emerge events—new clusters increase adoption-path uncertainty.",
                }
            )
        if die:
            drivers.append(
                {
                    "axis": "Technology displacement",
                    "description": (
                        f"{len(die)} declining topic(s) signal potential displacement of incumbent approaches."
                    ),
                    "why": "Derived from die events—fading clusters imply replacement risk for legacy tech.",
                }
            )

    if len(drivers) < 2:
        kws = clusters[0].get("keywords", ["AI"]) if clusters else ["AI"]
        drivers.extend(
            [
                {
                    "axis": "Regulatory clarity",
                    "description": "Policy and standards may accelerate or block deployment of key clusters.",
                    "why": "Default driver when causal events were insufficient—common foresight axis.",
                },
                {
                    "axis": "Investment intensity",
                    "description": f"Funding flows around '{', '.join(kws[:3])}' could diverge sharply across scenarios.",
                    "why": "Default driver based on dominant cluster keywords and publication concentration.",
                },
            ]
        )
    return drivers[:2]


def _horizon_phrase(foresight: dict[str, Any] | None) -> str:
    year = (foresight or {}).get("horizon_year")
    if year:
        return f" Frame all impacts toward the {year} forecast horizon."
    return ""


def _focus_phrase(foresight: dict[str, Any] | None) -> str:
    label = (foresight or {}).get("topic_label", "").strip()
    if label:
        return f" The user's focus domain is «{label}» — stay within this domain, not telecommunications unless the corpus is telecom."
    return ""


def generate_scenarios(
    drivers: list[dict],
    clusters: list[dict],
    events: list[dict],
    foresight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    axis_a = drivers[0]["axis"] if drivers else "Adoption"
    axis_b = drivers[1]["axis"] if len(drivers) > 1 else "Regulation"
    labels = [c.get("label", "") for c in clusters[:6]]
    event_summary = "; ".join(f"{e.get('type')}:{','.join((e.get('keywords') or [])[:2])}" for e in events[:6])

    scenarios = {}
    quadrants = [
        ("optimistic", "high", "high"),
        ("disruptive", "high", "low"),
        ("constrained", "low", "high"),
        ("stagnant", "low", "low"),
    ]
    for key, a_level, b_level in quadrants:
        tone = SCENARIO_TONES[key]
        system = (
            f"You are a technology foresight analyst writing a {tone['title']} scenario in 2-3 sentences.\n"
            "Name specific technologies from the clusters. Explain causal drivers (adoption, regulation, "
            "competition, breakthroughs). Avoid vague phrases like 'corpus patterns' or 'cross-pollination'."
            f"{_focus_phrase(foresight)}{_horizon_phrase(foresight)}"
        )
        user = (
            f"Driver A ({axis_a}): {a_level}. Driver B ({axis_b}): {b_level}.\n"
            f"Focus domain: {(foresight or {}).get('topic_label') or 'general technology foresight'}.\n"
            f"Forecast horizon: {(foresight or {}).get('horizon_year') or 'next 5–10 years'}.\n"
            f"Technology clusters: {', '.join(labels)}.\n"
            f"Recent evolution events: {event_summary}"
        )
        narrative = llm_chat(system, user, max_tokens=260)
        scenarios[key] = {
            "tone": key,
            "title": tone["title"],
            "color": tone["color"],
            "narrative": narrative,
            "why": (
                f"Narrative generated for {a_level} {axis_a} × {b_level} {axis_b} quadrant "
                "using cluster themes and detected evolution events."
            ),
        }
    return {
        "drivers": drivers,
        "axis_labels": {"x": axis_a, "y": axis_b},
        "scenarios": scenarios,
        "why": "Four scenarios span the 2×2 space of the two largest uncertainty drivers extracted from causal events.",
    }


def _cluster_focus_score(cluster: dict, focus_terms: list[str]) -> float:
    if not focus_terms:
        return 0.0
    hay = " ".join(
        [
            cluster.get("label") or "",
            " ".join(cluster.get("keywords") or []),
        ]
    ).lower()
    return sum(1.0 for term in focus_terms if term.lower() in hay)


def _main_technology(clusters: list[dict], foresight: dict[str, Any] | None = None) -> dict[str, Any]:
    if not clusters:
        label = (foresight or {}).get("topic_label") or "Core technology"
        return {"label": label, "topic_id": 0, "keywords": (foresight or {}).get("topic_terms", [])}

    focus_terms = (foresight or {}).get("topic_terms") or []
    if focus_terms:
        main = max(
            clusters,
            key=lambda c: (_cluster_focus_score(c, focus_terms) * 100) + c.get("count", 0),
        )
    else:
        main = max(clusters, key=lambda c: c.get("count", 0))

    cluster_label = main.get("label") or ", ".join((main.get("keywords") or [])[:3])
    focus_label = (foresight or {}).get("topic_label", "").strip()
    display_label = focus_label or cluster_label

    return {
        "label": display_label,
        "cluster_label": cluster_label,
        "topic_id": main.get("topic_id"),
        "keywords": main.get("keywords", [])[:8],
        "lifecycle_stage": main.get("lifecycle_stage", "maturity"),
    }


def build_impact_trees(
    scenarios: dict[str, Any],
    clusters: list[dict],
    *,
    lifecycle: dict[str, Any] | None = None,
    timeline: dict[str, list[dict]] | None = None,
    events: list[dict] | None = None,
    influence: list[dict] | None = None,
    weak_signals: list[dict] | None = None,
    foresight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build per-scenario trees: main tech ← evolving adjacent techs ← forecast impacts."""
    lifecycle = lifecycle or {}
    timeline = timeline or {}
    events = events or []
    influence = influence or []
    weak_signals = weak_signals or []

    main = _main_technology(clusters, foresight)
    all_paths = discover_impact_paths(
        main, clusters, lifecycle, timeline, events, influence, weak_signals
    )

    trees = {}
    for key, sc in scenarios.get("scenarios", {}).items():
        scenario_paths = select_paths_for_scenario(all_paths, key)
        scenario_paths = enrich_scenario_paths_with_llm(
            scenario_paths,
            main,
            sc["title"],
            sc.get("narrative", ""),
            foresight=foresight,
        )
        tree = build_tree_from_paths(main, scenario_paths, sc["title"], key)
        tree = _normalize_tree(tree, main["label"])

        trees[key] = {
            "tree": tree,
            "main_technology": main["label"],
            "paths_discovered": len(all_paths),
            "paths_in_scenario": len(scenario_paths),
            "branch_count": tree.get("branch_count", 0),
            "why": (
                f"This {sc['title']} tree shows {tree.get('branch_count', 0)} branch(es) from "
                f"{len(scenario_paths)} prioritized path(s) out of {len(all_paths)} discovered in the corpus "
                f"(influence edges, change events, clusters, weak signals). Each scenario ranks paths differently."
            ),
        }

    return trees


def _normalize_tree(tree: dict, main_label: str) -> dict:
    """Ensure node types and root label are consistent."""
    tree["node_type"] = "main"
    tree["name"] = tree.get("name") or main_label
    for child in tree.get("children") or []:
        child.setdefault("node_type", "evolving")
        child.setdefault("trend", "evolving")
        child.setdefault("path_sources", [])
        for impact in child.get("children") or []:
            impact.setdefault("node_type", "impact")
            impact.setdefault("sector", "Innovation")
            impact.setdefault("why", "")
            impact.setdefault("how", "")
            impact.setdefault("llm_source", "")
            impact["children"] = []
    return tree
