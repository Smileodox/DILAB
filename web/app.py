import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="DiLab Foresight Dashboard")

DATA_DIR = Path(__file__).parent.parent / "data" / "outputs"
STATIC_DIR = Path(__file__).parent / "static"


def load(name: str) -> dict:
    with open(DATA_DIR / f"{name}.json") as f:
        return json.load(f)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/overview")
async def overview():
    kb = load("kb_state")
    merge = load("merge_state")
    cib = load("cib_state")
    final = load("final_analysis")
    drivers = merge["unified_drivers"]
    origins = {}
    for d in drivers:
        origins[d["origin"]] = origins.get(d["origin"], 0) + 1
    return {
        "sources": len(kb["sources"]),
        "chunks": len(kb.get("chunks", {})),
        "drivers_total": len(drivers),
        "drivers_by_origin": origins,
        "cib_drivers": len(cib["driver_names"]),
        "cib_pairs": len(cib["entries"]),
        "scenarios": len(final["scenarios"]),
    }


@app.get("/api/sources")
async def sources():
    kb = load("kb_state")
    chunk_counts = {}
    for chunk in kb["chunks"].values():
        sid = chunk["source_id"]
        chunk_counts[sid] = chunk_counts.get(sid, 0) + 1
    result = []
    for src in kb["sources"].values():
        result.append({**src, "chunk_count": chunk_counts.get(src["id"], 0)})
    return result


@app.get("/api/drivers")
async def drivers():
    merge = load("merge_state")
    return merge["unified_drivers"]


@app.get("/api/bom")
async def bom():
    bom_data = load("bom_state")
    nodes = bom_data["bom_nodes"]
    root_id = bom_data["root_id"]
    driver_ids = {d["id"] for d in bom_data["bom_drivers"]}

    children_map = {}
    for nid, n in nodes.items():
        pid = n.get("parent_id")
        if pid:
            children_map.setdefault(pid, []).append(nid)

    def build_tree(nid):
        n = nodes[nid]
        return {
            "id": nid,
            "name": n["name"],
            "level": n.get("level", 0),
            "is_driver": nid in driver_ids or n.get("is_driver", False),
            "description": n.get("description", "")[:200],
            "children": [build_tree(cid) for cid in children_map.get(nid, [])],
        }

    return {
        "tree": build_tree(root_id),
        "total_nodes": len(nodes),
        "total_drivers": len(bom_data["bom_drivers"]),
    }


@app.get("/api/cib")
async def cib():
    return load("cib_state")


@app.get("/api/scenarios")
async def scenarios():
    final = load("final_analysis")
    merged = []
    for s, a in zip(final["scenarios"], final["assessments"]):
        merged.append({**s, "assessment": a})
    return merged


@app.get("/api/traceability/{scenario_id}")
async def traceability(scenario_id: str):
    final = load("final_analysis")
    kb = load("kb_state")
    merge = load("merge_state")

    scenario = next((s for s in final["scenarios"] if s["id"] == scenario_id), None)
    assessment = next((a for a in final["assessments"] if a["scenario_id"] == scenario_id), None)
    if not scenario:
        return {"error": "Scenario not found"}

    driver_by_id = {d["id"]: d for d in merge["unified_drivers"]}

    assumptions = []
    for a in scenario["assumptions"]:
        driver = driver_by_id.get(a["driver_id"])
        assumptions.append({
            "state": a["state"],
            "description": a["description"],
            "driver": driver,
        })

    source_chain = []
    seen_sources = set()
    for chunk_id in scenario["source_chunk_ids"]:
        chunk = kb["chunks"].get(chunk_id)
        if chunk:
            src = kb["sources"].get(chunk["source_id"])
            if src and src["id"] not in seen_sources:
                seen_sources.add(src["id"])
                source_chain.append({
                    "source": src,
                    "chunk_id": chunk_id,
                    "chunk_preview": chunk["content"][:200],
                })

    return {
        "scenario": scenario,
        "assessment": assessment,
        "assumptions": assumptions,
        "source_chain": source_chain,
    }


@app.get("/api/export")
async def export_all():
    from datetime import datetime
    return {
        "overview": await overview(),
        "sources": await sources(),
        "drivers": await drivers(),
        "cib": await cib(),
        "scenarios": await scenarios(),
        "exported_at": datetime.now().isoformat(),
    }


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
