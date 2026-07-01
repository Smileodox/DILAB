"""Helpers to flatten trees and graphs for JSON export and RAG."""
from __future__ import annotations

from typing import Any

from app.models.schemas import ImpactTreeNode, TechnologySignal


def impact_node_to_dict(node: ImpactTreeNode) -> dict[str, Any]:
    return node.model_dump(mode="json")


def extract_evolution_paths(
    node: ImpactTreeNode,
    ancestors: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect root-to-leaf paths through the impact tree (for RAG / downstream LLM)."""
    ancestors = ancestors or []
    step = {
        "id": node.id,
        "label": node.label,
        "node_type": node.node_type,
        "impact_score": node.impact_score,
        "evolution_year": node.evolution_year,
        "peak_effect_year": node.peak_effect_year,
        "evolution_speed": node.evolution_speed,
        "relation_probability": node.relation_probability,
        "contributing_technologies": node.contributing_technologies,
        "is_scenario_seed": node.is_scenario_seed,
        "path_id": node.path_id,
    }
    path_so_far = [*ancestors, step]

    if not node.children:
        return [{
            "path_id": node.path_id or node.id,
            "steps": path_so_far,
            "final_outcome": node.label,
            "target_year": node.target_year,
            "evolution_speed": node.evolution_speed,
            "contributing_technologies": node.contributing_technologies,
            "relation_probability": node.relation_probability,
            "is_scenario_seed": node.is_scenario_seed,
            "scenario_cluster_hint": node.scenario_cluster_hint,
        }]

    paths: list[dict[str, Any]] = []
    for child in node.children:
        paths.extend(extract_evolution_paths(child, path_so_far))
    return paths


def scenario_seed_to_dict(node: ImpactTreeNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "label": node.label,
        "path_id": node.path_id,
        "evolved_outcome": node.label,
        "target_year": node.target_year,
        "evolution_speed": node.evolution_speed,
        "relation_probability": node.relation_probability,
        "contributing_technologies": node.contributing_technologies,
        "relationship_to_main": node.relationship_to_main,
        "scenario_cluster_hint": node.scenario_cluster_hint,
        "dvi_composite": node.dvi_composite,
        "growth_rate": node.growth_rate,
        "maturity_pct": node.maturity_pct,
    }


def group_signals_by_type(signals: list[TechnologySignal]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for signal in signals:
        key = signal.dvi.signal_type.value
        grouped.setdefault(key, []).append(signal.name)
    return grouped


def signal_summary(signals: list[TechnologySignal]) -> dict[str, Any]:
    if not signals:
        return {"count": 0}
    composites = [s.dvi.composite for s in signals]
    return {
        "count": len(signals),
        "avg_composite_dvi": round(sum(composites) / len(composites), 4),
        "strongest_signal": max(signals, key=lambda s: s.dvi.composite).name,
        "signal_type_counts": {
            st: sum(1 for s in signals if s.dvi.signal_type.value == st)
            for st in sorted({s.dvi.signal_type.value for s in signals})
        },
    }
