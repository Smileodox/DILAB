"""
Cascade propagation analysis on the technology web graph.
Computes how changes at any ST/industry node propagate to Main Technology (M).
"""

from __future__ import annotations

from collections import defaultdict

from tdi.models.schemas import GraphEdge, GraphNode, PropagationPath


def _build_adjacency(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> tuple[dict[str, str], dict[str, list[tuple[str, float, str]]]]:
    labels = {n.id: n.label for n in nodes}
    adj: dict[str, list[tuple[str, float, str]]] = defaultdict(list)

    for e in edges:
        adj[e.source].append((e.target, e.probability, e.relationship))
        adj[e.target].append((e.source, e.probability, e.relationship))

    return labels, adj


def _find_best_path_to_target(
    start_id: str,
    target_id: str,
    adj: dict[str, list[tuple[str, float, str]]],
    labels: dict[str, str],
    max_depth: int = 5,
) -> tuple[float, list[str], list[str]]:
    """DFS: best cascade probability = max product of edge probabilities along path."""
    if start_id == target_id:
        return 1.0, [labels[target_id]], [target_id]

    best_prob = 0.0
    best_labels: list[str] = []
    best_ids: list[str] = []

    def dfs(current: str, path_ids: list[str], path_labels: list[str], prob: float, depth: int) -> None:
        nonlocal best_prob, best_labels, best_ids
        if depth > max_depth:
            return
        if current == target_id:
            if prob > best_prob:
                best_prob = prob
                best_labels = list(path_labels)
                best_ids = list(path_ids)
            return
        for neighbor, edge_p, _rel in adj.get(current, []):
            if neighbor in path_ids:
                continue
            cascade_p = prob * edge_p
            if cascade_p < best_prob:
                continue
            dfs(
                neighbor,
                path_ids + [neighbor],
                path_labels + [labels.get(neighbor, neighbor)],
                cascade_p,
                depth + 1,
            )

    dfs(start_id, [start_id], [labels.get(start_id, start_id)], 1.0, 0)
    return best_prob, best_labels, best_ids


def compute_propagation_paths(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    main_technology_id: str,
) -> list[PropagationPath]:
    labels, adj = _build_adjacency(nodes, edges)
    main_label = labels.get(main_technology_id, "Main Technology")
    paths: list[PropagationPath] = []

    trigger_types = {
        "main_technology", "sub_technology", "technology",
        "industry", "policy", "standard", "spectrum_band",
    }

    for node in nodes:
        if node.id == main_technology_id:
            continue
        if node.node_type not in trigger_types:
            continue

        prob, path_labels, path_ids = _find_best_path_to_target(
            node.id, main_technology_id, adj, labels,
        )
        if prob <= 0 or len(path_ids) < 2:
            continue

        paths.append(PropagationPath(
            source_id=node.id,
            source_label=node.label,
            source_type=node.node_type,
            target_id=main_technology_id,
            target_label=main_label,
            path_labels=path_labels,
            path_node_ids=path_ids,
            cascade_probability=round(prob, 4),
        ))

    deduped: dict[str, PropagationPath] = {}
    for p in paths:
        existing = deduped.get(p.source_id)
        if not existing or p.cascade_probability > existing.cascade_probability:
            deduped[p.source_id] = p

    return sorted(deduped.values(), key=lambda p: p.cascade_probability, reverse=True)


def annotate_node_cascade_impact(
    nodes: list[GraphNode],
    paths: list[PropagationPath],
    main_technology_id: str,
) -> list[GraphNode]:
    impact_map = {p.source_id: p.cascade_probability for p in paths}
    updated = []
    for node in nodes:
        props = dict(node.properties)
        if node.id == main_technology_id:
            props["cascade_impact_on_main"] = 1.0
        elif node.id in impact_map:
            props["cascade_impact_on_main"] = impact_map[node.id]
        updated.append(node.model_copy(update={"properties": props}))
    return updated
