import json
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

app = FastAPI(title="DiLab Foresight Dashboard")

AUTH_PASSWORD = os.environ.get("APP_PASSWORD", "")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not AUTH_PASSWORD:
        return await call_next(request)
    import base64
    auth = request.headers.get("authorization", "")
    if auth.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            _, password = decoded.split(":", 1)
            if secrets.compare_digest(password, AUTH_PASSWORD):
                return await call_next(request)
        except Exception:
            pass
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="R&S Foresight"'},
    )

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

    morph_manifs = 0
    consistency_seeds = 0
    try:
        morph = load("morphbox_state")
        morph_manifs = len(morph.get("all_manifestations", []))
    except FileNotFoundError:
        pass
    try:
        cons = load("consistency_state")
        consistency_seeds = len(cons.get("configs", []))
    except FileNotFoundError:
        cons = {}

    panel_meta = cib.get("panel_metadata", {})
    total_fps = cons.get("total_fixed_points", 0)
    mc_samples = cons.get("n_mc_samples", 0)

    return {
        "sources": len(kb["sources"]),
        "chunks": len(kb.get("chunks", {})),
        "drivers_total": len(drivers),
        "drivers_by_origin": origins,
        "cib_drivers": len(cib["driver_names"]),
        "cib_pairs": len(cib["entries"]),
        "scenarios": len(final["scenarios"]),
        "manifestations": morph_manifs,
        "consistency_seeds": consistency_seeds,
        "panel_mode": panel_meta.get("mode", "single"),
        "n_personas": panel_meta.get("n_personas", 1),
        "mc_samples": mc_samples,
        "total_fixed_points": total_fps,
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


@app.get("/api/morphbox")
async def morphbox():
    morph = load("morphbox_state")
    merge = load("merge_state")
    cib = load("cib_state")
    driver_by_id = {d["id"]: d for d in merge["unified_drivers"]}
    cib_name_by_id = dict(zip(cib["driver_ids"], cib["driver_names"]))
    drivers_out = []
    for did in morph["drivers"]:
        d = driver_by_id.get(did, {})
        manif_ids = morph["manifestations"].get(did, [])
        manifs = [m for m in morph["all_manifestations"] if m["id"] in manif_ids]
        name = d.get("name") or cib_name_by_id.get(did) or did
        drivers_out.append({
            "id": did,
            "name": name,
            "origin": d.get("origin", ""),
            "confidence": d.get("confidence", ""),
            "manifestations": manifs,
        })
    return {
        "drivers": drivers_out,
        "total_manifestations": len(morph["all_manifestations"]),
    }


@app.get("/api/consistency")
async def consistency():
    try:
        cons = load("consistency_state")
    except FileNotFoundError:
        return {"configs": [], "total_fixed_points": 0}
    merge = load("merge_state")
    morph = load("morphbox_state")
    driver_by_id = {d["id"]: d for d in merge["unified_drivers"]}
    manif_by_id = {m["id"]: m for m in morph["all_manifestations"]}

    configs_out = []
    for cfg in cons.get("configs", []):
        config = cfg["configuration"]
        entries = []
        for did, mid in config.items():
            d = driver_by_id.get(did, {})
            m = manif_by_id.get(mid, {})
            entries.append({
                "driver_id": did,
                "driver_name": d.get("name", did),
                "manifestation_id": mid,
                "manifestation_label": m.get("label", mid),
                "plausibility": m.get("plausibility", ""),
            })
        configs_out.append({
            "entries": entries,
            "consistency_score": cfg.get("consistency_score", 0),
            "scenario_type": cfg.get("scenario_type", "evolutionary"),
        })
    return {
        "configs": configs_out,
        "total_fixed_points": cons.get("total_fixed_points", len(cons.get("configs", []))),
    }


@app.get("/api/cib")
async def cib():
    data = load("cib_state")
    n = len(data["driver_names"])
    std_matrix = [[0.0] * n for _ in range(n)]
    for entry in data.get("entries", []):
        if entry.get("score_std", 0) > 0:
            a_idx = data["driver_ids"].index(entry["driver_a_id"])
            b_idx = data["driver_ids"].index(entry["driver_b_id"])
            std_matrix[a_idx][b_idx] = entry["score_std"]
    data["std_matrix"] = std_matrix
    return data


@app.get("/api/scenarios")
async def scenarios():
    final = load("final_analysis")
    rankings_by_id = {
        r["scenario_id"]: r
        for r in final.get("mcda", {}).get("rankings", [])
    }
    merged = []
    for s, a in zip(final["scenarios"], final["assessments"]):
        ranking = rankings_by_id.get(s["id"], {})
        merged.append({
            **s,
            "assessment": a,
            "topsis_closeness": ranking.get("topsis_closeness", 0),
            "rank": ranking.get("rank", 0),
        })
    merged.sort(key=lambda x: x["rank"])
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


_cib_3d_cache = {"mtime": 0, "data": None}


@app.get("/api/cib/3d")
async def cib_3d():
    # Pre-computed file (used in Azure deploy where umap isn't available)
    try:
        return load("cib_3d")
    except FileNotFoundError:
        pass

    cib_path = DATA_DIR / "cib_state.json"
    try:
        mtime = cib_path.stat().st_mtime
    except FileNotFoundError:
        return {"nodes": [], "edges": [], "stats": {}}

    if _cib_3d_cache["mtime"] == mtime and _cib_3d_cache["data"]:
        return _cib_3d_cache["data"]

    import numpy as np
    from umap import UMAP

    data = load("cib_state")
    matrix = data["matrix"]
    n = len(matrix)
    names = data["driver_names"]
    ids = data["driver_ids"]
    influence = data.get("influence", {})
    dependence = data.get("dependence", {})

    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            score = abs(matrix[i][j]) + abs(matrix[j][i])
            dist[i][j] = 1.0 / (1.0 + score)
    np.fill_diagonal(dist, 0)

    reducer = UMAP(
        n_components=3,
        n_neighbors=min(10, n - 1),
        min_dist=0.3,
        metric="precomputed",
        random_state=42,
    )
    coords = reducer.fit_transform(dist)

    nodes = []
    for i in range(n):
        nodes.append({
            "id": ids[i],
            "name": names[i],
            "x": round(float(coords[i, 0]), 4),
            "y": round(float(coords[i, 1]), 4),
            "z": round(float(coords[i, 2]), 4),
            "influence": influence.get(ids[i], 0),
            "dependence": dependence.get(ids[i], 0),
        })

    edges = []
    for i in range(n):
        for j in range(n):
            if i != j and matrix[i][j] != 0:
                edges.append({
                    "source": ids[i],
                    "target": ids[j],
                    "score": matrix[i][j],
                })

    promoting = sum(1 for e in edges if e["score"] > 0)
    inhibiting = sum(1 for e in edges if e["score"] < 0)
    strongest_pos = max(edges, key=lambda e: e["score"]) if promoting else None
    strongest_neg = min(edges, key=lambda e: e["score"]) if inhibiting else None
    most_influential = max(nodes, key=lambda n: n["influence"])
    name_by_id = dict(zip(ids, names))

    stats = {
        "total_edges": len(edges),
        "promoting": promoting,
        "inhibiting": inhibiting,
        "strongest_promoting": f"{name_by_id[strongest_pos['source']]} → {name_by_id[strongest_pos['target']]} ({strongest_pos['score']:+d})" if strongest_pos else None,
        "strongest_inhibiting": f"{name_by_id[strongest_neg['source']]} → {name_by_id[strongest_neg['target']]} ({strongest_neg['score']:+d})" if strongest_neg else None,
        "most_influential": most_influential["name"],
    }

    result = {"nodes": nodes, "edges": edges, "stats": stats}
    _cib_3d_cache["mtime"] = mtime
    _cib_3d_cache["data"] = result
    return result


@app.get("/api/landscape")
async def landscape():
    try:
        return load("landscape_state")
    except FileNotFoundError:
        return {"points": [], "similarity_matrix": [], "metadata": {}}


@app.get("/api/strategic_framing")
async def strategic_framing():
    try:
        return load("strategic_framing")
    except FileNotFoundError:
        return {"critical_uncertainties": [], "no_regret_moves": [], "scenario_strategy": [], "recommended_priority": {}}


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


@app.get("/{path:path}")
async def spa_fallback(path: str):
    return FileResponse(STATIC_DIR / "index.html")
