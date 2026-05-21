"""BOM Decomposition pipeline step.

Input: data/outputs/kb_state.json (or fixture)
Output: data/outputs/bom_state.json

Owner: Branch 2 (feature/driver-finding)
"""
from __future__ import annotations

import json
import os

from src.config import CHROMA_PERSIST_DIR, MAX_RAG_CHUNKS, BOM_MAX_DEPTH
from src.llm import embed, safe_chat_json
from src.models.drivers import BOMNode, TechDriver, DriverOrigin, DriverConfidence
from src.models.common import KBPool, stable_id
from src.rag import get_collection, retrieve, format_rag_chunks
from src.prompts.bom import BOM_DECOMPOSE, BOM_CLASSIFY_DRIVER


def decompose(
    node: BOMNode,
    bom_nodes: dict[str, BOMNode],
    collection,
    max_depth: int = BOM_MAX_DEPTH,
) -> BOMNode:
    """Recursively decompose a BOM node into sub-components.

    Extracted from NB02 Cell 2.
    """
    if node.level >= max_depth:
        return node

    # RAG: retrieve chunks relevant to this specific component
    query = f"{node.name} {node.description} components sub-components technology"
    rag_chunks = retrieve(collection, query, pool="product", n=3)
    rag_text = format_rag_chunks(rag_chunks)

    # build parent context
    parent_context = (
        "Top-level product"
        if node.parent_id is None
        else f"Part of: {bom_nodes[node.parent_id].name}"
    )

    prompt = BOM_DECOMPOSE.format(
        parent_context=parent_context,
        component_name=node.name,
        component_description=node.description,
        rag_chunks=rag_text,
    )

    response = safe_chat_json(
        prompt,
        system="You are a technical analyst decomposing spectrum monitoring equipment into sub-components.",
    )

    for comp in response.get("components", []):
        child = BOMNode(
            id=stable_id(node.id, comp["name"]),
            name=comp["name"],
            description=comp.get("description", ""),
            level=node.level + 1,
            parent_id=node.id,
            source_chunk_ids=response.get("source_chunk_ids_used", []),
        )
        bom_nodes[child.id] = child
        node.children_ids.append(child.id)

        indent = "  " * child.level
        leaf_marker = " (leaf)" if comp.get("is_leaf") else ""
        print(f"{indent}├── {child.name}{leaf_marker}")

        if not comp.get("is_leaf", False):
            decompose(child, bom_nodes, collection, max_depth)

    return node


def get_bom_path(node_id: str, bom_nodes: dict[str, BOMNode]) -> str:
    """Trace path from root to this node.

    Extracted from NB02 Cell 6.
    """
    path = []
    current = bom_nodes[node_id]
    while current:
        path.append(current.name)
        current = bom_nodes.get(current.parent_id) if current.parent_id else None
    return " → ".join(reversed(path))


def classify_drivers(
    leaves: list[BOMNode],
    bom_nodes: dict[str, BOMNode],
) -> list[TechDriver]:
    """Classify leaf nodes as tech drivers.

    Extracted from NB02 Cell 6.
    """
    bom_drivers: list[TechDriver] = []

    for leaf in leaves:
        bom_path = get_bom_path(leaf.id, bom_nodes)
        prompt = BOM_CLASSIFY_DRIVER.format(
            name=leaf.name,
            description=leaf.description,
            bom_path=bom_path,
        )
        result = safe_chat_json(
            prompt,
            system="You are a technology analyst evaluating whether components represent active technology drivers.",
        )

        leaf.is_tech_driver = result.get("is_tech_driver", False)
        marker = "DRIVER" if leaf.is_tech_driver else "passive"
        print(f"  [{marker}] {leaf.name} — {result.get('reasoning', '')[:80]}")

        if leaf.is_tech_driver:
            driver = TechDriver(
                id=stable_id("bom", leaf.name),
                name=leaf.name,
                description=f"{leaf.description}. {result.get('reasoning', '')}",
                origin=DriverOrigin.BOM,
                confidence=DriverConfidence.MEDIUM,
                bom_node_id=leaf.id,
                source_chunk_ids=leaf.source_chunk_ids,
            )
            bom_drivers.append(driver)

    print(f"\n=== {len(bom_drivers)} Tech Drivers identified from BOM ===")
    return bom_drivers


def dedup_drivers(bom_drivers: list[TechDriver]) -> list[TechDriver]:
    """Deduplicate drivers by normalized name, merging source_chunk_ids.

    Extracted from NB02 Cell 7.
    """
    seen: dict[str, TechDriver] = {}
    for d in bom_drivers:
        key = d.name.lower().strip()
        if key in seen:
            for sid in d.source_chunk_ids:
                if sid not in seen[key].source_chunk_ids:
                    seen[key].source_chunk_ids.append(sid)
        else:
            seen[key] = d

    deduped = list(seen.values())
    print(f"After dedup: {len(deduped)} unique BOM drivers")
    return deduped


def run(
    kb_state_path: str = "data/outputs/kb_state.json",
    output_path: str = "data/outputs/bom_state.json",
) -> dict:
    """Run full BOM decomposition pipeline."""
    collection = get_collection()

    with open(kb_state_path) as f:
        kb_state = json.load(f)

    print(f"KB: {len(kb_state['sources'])} sources, {len(kb_state['chunks'])} chunks")

    bom_nodes: dict[str, BOMNode] = {}
    root = BOMNode(
        id=stable_id("root", "R&S ESMW Ultra Wideband Monitoring Receiver"),
        name="R&S ESMW Ultra Wideband Monitoring Receiver",
        description=(
            "Next generation ultra wideband monitoring receiver for spectrum monitoring "
            "and direction finding. Frequency range 8 kHz to 40 GHz, up to 2 GHz "
            "real-time bandwidth, panorama scan at 2.6 THz/s, 75ns minimum signal "
            "duration for 100% POI, I/Q streaming via 100GE, AoA direction finding, "
            "TDOA localization, ITU-compliant."
        ),
        level=0,
    )
    bom_nodes[root.id] = root

    print(f"ROOT: {root.name} (id={root.id})\n")
    decompose(root, bom_nodes, collection)
    print(f"\nTotal BOM nodes: {len(bom_nodes)}")

    # classify leaf nodes as tech drivers
    leaves = [n for n in bom_nodes.values() if not n.children_ids]
    print(f"\nFound {len(leaves)} leaf nodes to classify\n")
    bom_drivers = classify_drivers(leaves, bom_nodes)
    bom_drivers = dedup_drivers(bom_drivers)

    state = {
        "bom_nodes": {k: v.model_dump(mode="json") for k, v in bom_nodes.items()},
        "bom_drivers": [d.model_dump(mode="json") for d in bom_drivers],
        "root_id": root.id,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nSaved {len(bom_nodes)} BOM nodes, {len(bom_drivers)} tech drivers")
    return state
