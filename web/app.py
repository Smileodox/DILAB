import json
import os
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response

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

# Knowledge bases the Landscape page can switch between. Each maps to the output dir its
# pipeline run wrote to. "spectrum" = the primary KB; "agriculture" = the domain-agnostic
# proof run (data/outputs_ag), present only if that proof has been run locally.
KB_DIRS = {
    "spectrum": DATA_DIR,
    "agriculture": DATA_DIR.parent / "outputs_ag",
}

# Scenario method -> (output-file suffix, landscape shape). "fixedpoint" = the small CIB
# fixed-point set (pairwise similarity heatmap); "sampled" = many configs with clusters +
# representatives (combinatorial soft-CIB and functional/CCA).
METHODS = {
    "cib": ("", "fixedpoint"),
    "combi": ("_combi", "sampled"),
    "zwicky": ("_zwicky", "sampled"),
}

# Per-KB file aliases: a KB that ran a different pipeline path stores schema-compatible
# artifacts under different names. Resolving centrally in load() keeps the endpoints generic.
FILE_ALIASES = {
    "agriculture": {  # ran the functional/Zwicky path → substitute its variants
        "merge_state": "functional_merge_state",
        "morphbox_state": "morphbox_zwicky_state",
    },
}

# Which output files a page needs (for the selected KB, after aliasing). Drives nav grey-out:
# a KB only offers a view if all of the view's files exist for it.
VIEW_REQUIREMENTS = {
    "/": ["kb_state", "merge_state", "cib_state", "final_analysis"],
    "/pipeline": ["kb_state", "merge_state", "cib_state", "final_analysis"],
    "/sources": ["kb_state"],
    "/drivers": ["merge_state"],
    "/bom": ["bom_state"],
    "/morphbox": ["morphbox_state", "merge_state"],
    "/cib": ["cib_state"],
    "/scenarios": ["final_analysis"],
    "/strategy": ["strategic_framing"],
    "/embeddings": ["cib_state"],
    "/archetypes": ["archetypes_state"],
    "/present": ["landscape_state_combi", "archetypes_state", "engine_validation_fields"],
    "/methodology": [],  # static content page — available for every KB (all([]) is True)
}


def _resolve(name: str, kb: str) -> Path:
    actual = FILE_ALIASES.get(kb, {}).get(name, name)
    return KB_DIRS.get(kb, DATA_DIR) / f"{actual}.json"


def load(name: str, kb: str = "spectrum") -> dict:
    with open(_resolve(name, kb)) as f:
        return json.load(f)


@app.exception_handler(FileNotFoundError)
async def _missing_file(request: Request, exc: FileNotFoundError):
    # A data file the endpoint needs does not exist for the selected KB → graceful sentinel
    # (the frontend greys such views out via /api/kbs `views`, this is the safety net).
    return JSONResponse({"unavailable": True}, status_code=200)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/overview")
async def overview(kb: str = "spectrum"):
    kb_data = load("kb_state", kb)
    merge = load("merge_state", kb)
    cib = load("cib_state", kb)
    final = load("final_analysis", kb)
    drivers = merge["unified_drivers"]
    origins = {}
    for d in drivers:
        origins[d["origin"]] = origins.get(d["origin"], 0) + 1

    morph_manifs = 0
    consistency_seeds = 0
    try:
        morph = load("morphbox_state", kb)
        morph_manifs = len(morph.get("all_manifestations", []))
    except FileNotFoundError:
        pass
    try:
        cons = load("consistency_state", kb)
        consistency_seeds = len(cons.get("configs", []))
    except FileNotFoundError:
        cons = {}

    panel_meta = cib.get("panel_metadata", {})
    total_fps = cons.get("total_fixed_points", 0)
    mc_samples = cons.get("n_mc_samples", 0)

    return {
        "sources": len(kb_data["sources"]),
        "chunks": len(kb_data.get("chunks", {})),
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
async def sources(kb: str = "spectrum"):
    kb_data = load("kb_state", kb)
    chunk_counts = {}
    for chunk in kb_data["chunks"].values():
        sid = chunk["source_id"]
        chunk_counts[sid] = chunk_counts.get(sid, 0) + 1
    result = []
    for src in kb_data["sources"].values():
        result.append({**src, "chunk_count": chunk_counts.get(src["id"], 0)})
    return result


@app.get("/api/drivers")
async def drivers(kb: str = "spectrum"):
    merge = load("merge_state", kb)
    return merge["unified_drivers"]


@app.get("/api/bom")
async def bom(kb: str = "spectrum"):
    bom_data = load("bom_state", kb)
    nodes = bom_data["bom_nodes"]
    root_id = bom_data["root_id"]
    # bom_drivers carry their own driver id; the BOM tree is keyed by bom_node_id.
    driver_ids = {d["bom_node_id"] for d in bom_data["bom_drivers"] if d.get("bom_node_id")}

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
            "description": (n.get("description", "")[:200] + "…"
                            if len(n.get("description", "")) > 200
                            else n.get("description", "")),
            "children": [build_tree(cid) for cid in children_map.get(nid, [])],
        }

    return {
        "tree": build_tree(root_id),
        "total_nodes": len(nodes),
        "total_drivers": len(bom_data["bom_drivers"]),
    }


@app.get("/api/morphbox")
async def morphbox(kb: str = "spectrum"):
    morph = load("morphbox_state", kb)
    merge = load("merge_state", kb)
    driver_by_id = {d["id"]: d for d in merge["unified_drivers"]}
    drivers_out = []
    for did in morph["drivers"]:
        d = driver_by_id.get(did, {})
        manif_ids = morph["manifestations"].get(did, [])
        manifs = [m for m in morph["all_manifestations"] if m["id"] in manif_ids]
        name = d.get("name") or did
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
async def consistency(kb: str = "spectrum"):
    try:
        cons = load("consistency_state", kb)
    except FileNotFoundError:
        return {"configs": [], "total_fixed_points": 0}
    merge = load("merge_state", kb)
    morph = load("morphbox_state", kb)
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
async def cib(kb: str = "spectrum"):
    data = load("cib_state", kb)
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
async def scenarios(kb: str = "spectrum", method: str = "cib"):
    suffix, shape = METHODS.get(method, ("", "fixedpoint"))
    if shape == "fixedpoint":
        try:
            final = load(f"final_analysis{suffix}", kb)
        except FileNotFoundError:
            return []
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

    # "sampled" shape (combinatorial / functional-CCA): all scenarios carry narratives;
    # MCDA rank/topsis exist only for the representatives.
    try:
        state = load(f"scenario_state{suffix}", kb)
    except FileNotFoundError:
        return []
    rankings_by_id = {}
    try:
        final = load(f"final_analysis{suffix}", kb)
        rankings_by_id = {
            r["scenario_id"]: r
            for r in final.get("mcda", {}).get("rankings", [])
        }
    except FileNotFoundError:
        pass
    merged = []
    for s in state.get("scenarios", []):
        ranking = rankings_by_id.get(s["id"], {})
        merged.append({
            **s,
            "topsis_closeness": ranking.get("topsis_closeness", 0),
            "rank": ranking.get("rank", 0),
        })
    return merged


@app.get("/api/traceability/{scenario_id}")
async def traceability(scenario_id: str, kb: str = "spectrum"):
    final = load("final_analysis", kb)
    kb_data = load("kb_state", kb)
    merge = load("merge_state", kb)

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

    # Some recorded chunk ids may not resolve in the current KB (re-ingested corpus);
    # count them so the UI can report resolution honestly instead of dropping silently.
    source_chain = []
    seen_sources = set()
    resolved_chunks = 0
    total_chunks = len(scenario["source_chunk_ids"])
    for chunk_id in scenario["source_chunk_ids"]:
        chunk = kb_data["chunks"].get(chunk_id)
        if chunk:
            resolved_chunks += 1
            src = kb_data["sources"].get(chunk["source_id"])
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
        "resolved_chunks": resolved_chunks,
        "total_chunks": total_chunks,
    }


_cib_3d_cache = {"mtime": 0, "data": None}


@app.get("/api/cib/3d")
async def cib_3d(kb: str = "spectrum"):
    # Pre-computed file (used in Azure deploy where umap isn't available)
    try:
        return load("cib_3d", kb)
    except FileNotFoundError:
        pass

    cib_path = _resolve("cib_state", kb)
    try:
        mtime = cib_path.stat().st_mtime
    except FileNotFoundError:
        return {"nodes": [], "edges": [], "stats": {}}

    if _cib_3d_cache["mtime"] == mtime and _cib_3d_cache["data"]:
        return _cib_3d_cache["data"]

    import numpy as np
    from umap import UMAP

    data = load("cib_state", kb)
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


@app.get("/api/kbs")
async def kbs():
    """KBs the dashboard can switch between: per-KB available scenario methods AND which
    page-views have data (after aliasing) so the nav can grey out the rest. Robust to a
    missing KB dir (e.g. agriculture only exists after the proof is run)."""
    out = []
    for kb_id, d in KB_DIRS.items():
        if not d.exists():
            continue
        methods = [m for m, (suffix, _) in METHODS.items()
                   if (d / f"landscape_state{suffix}.json").exists()]
        if not methods:
            continue
        views = [path for path, reqs in VIEW_REQUIREMENTS.items()
                 if all(_resolve(r, kb_id).exists() for r in reqs)]
        views.append("/landscape")  # has at least one method (checked above)
        label = kb_id
        prof = d / "domain_profile.json"
        if prof.exists():
            try:
                with open(prof) as f:
                    label = json.load(f).get("domain") or kb_id
            except Exception:
                pass
        out.append({"id": kb_id, "label": label, "methods": methods,
                    "views": sorted(set(views))})
    return out


@app.get("/api/landscape")
async def landscape(kb: str = "spectrum", method: str = "cib"):
    suffix, _ = METHODS.get(method, ("", "fixedpoint"))
    try:
        return load(f"landscape_state{suffix}", kb)
    except FileNotFoundError:
        return {"points": [], "similarity_matrix": [], "metadata": {}}


@app.get("/api/archetypes")
async def archetypes(kb: str = "spectrum"):
    """Named archetypes (HDBSCAN+ordinal dense-core clusters) + the honest continuum halo."""
    try:
        return load("archetypes_state", kb)
    except FileNotFoundError:
        return {"unavailable": True, "archetypes": []}


@app.get("/api/landscape_combi")
async def landscape_combi():
    """Combinatorial-method landscape (many soft-CIB scenarios + clusters)."""
    try:
        return load("landscape_state_combi")
    except FileNotFoundError:
        return {"points": [], "similarity_matrix": [], "metadata": {}}


@app.get("/api/scenarios_combi")
async def scenarios_combi():
    """All combinatorial scenarios (with narratives); MCDA rank/topsis for representatives."""
    try:
        combi = load("scenario_state_combi")
    except FileNotFoundError:
        return []
    rankings_by_id = {}
    try:
        final = load("final_analysis_combi")
        rankings_by_id = {
            r["scenario_id"]: r
            for r in final.get("mcda", {}).get("rankings", [])
        }
    except FileNotFoundError:
        pass
    merged = []
    for s in combi.get("scenarios", []):
        ranking = rankings_by_id.get(s["id"], {})
        merged.append({
            **s,
            "topsis_closeness": ranking.get("topsis_closeness", 0),
            "rank": ranking.get("rank", 0),
        })
    return merged


@app.get("/api/strategic_framing")
async def strategic_framing(kb: str = "spectrum"):
    try:
        return load("strategic_framing", kb)
    except FileNotFoundError:
        return {"critical_uncertainties": [], "no_regret_moves": [], "scenario_strategy": [], "recommended_priority": {}}


# ---------------------------------------------------------------------------
# Presentation mode (/present) — one precomputed bundle so the live talk never
# waits on a fetch. Everything is derived from the persisted final-run artifacts.
# ---------------------------------------------------------------------------

# The example driver whose journey the presentation follows through every stage.
_PRESENT_DRIVER_ID = "f33ab61e5a83"  # "Shift to dynamic shared and harmonised spectrum access"
_present_cache: dict = {"mtime": None, "data": None}


def _build_present_bundle(kb: str) -> dict:
    merge = load("merge_state", kb)
    morph = load("morphbox_state", kb)
    cib_data = load("cib_state", kb)
    kb_data = load("kb_state", kb)
    land = load("landscape_state_combi", kb)
    scen = load("scenario_state_combi", kb)["scenarios"]
    arch = load("archetypes_state", kb)
    validation = load("engine_validation_fields", kb)
    ov = load("kb_state", kb)  # sources/chunks counts come from kb_state directly

    did = _PRESENT_DRIVER_ID
    driver = next(d for d in merge["unified_drivers"] if d["id"] == did)

    # --- Journey: source evidence -------------------------------------------------
    chunk_ids = driver.get("source_chunk_ids", [])
    by_source: dict[str, list] = {}
    resolved = 0
    for cid in chunk_ids:
        ch = kb_data["chunks"].get(cid)
        if ch:
            resolved += 1
            src = kb_data["sources"].get(ch["source_id"], {})
            by_source.setdefault(src.get("title", "?"), []).append(ch)
    top_sources = sorted(by_source.items(), key=lambda kv: -len(kv[1]))

    def _clean_preview(text: str) -> str | None:
        # Strip private-use glyphs (render as tofu boxes), collapse whitespace, then
        # start the excerpt at the first sentence that reads like prose - chunk starts
        # are often running page headers ("RSPG25-006 FINAL 33", "74 THE ROAD TO 5G").
        t = "".join(c for c in text if not ("\ue000" <= c <= "\uf8ff")).strip()
        t = " ".join(t.split())
        sentences = re.split(r"(?<=[.!?]) +", t)
        for i, s in enumerate(sentences):
            if re.match(r"^[A-Z][a-z]", s) and len(s.split()) >= 8 and "http" not in s.lower():
                out = " ".join(sentences[i:])
                return out[:260] if len(out) >= 120 else None
        return None

    chunk_previews = []
    for title, chunks in top_sources[:4]:
        picked = 0
        for ch in chunks:
            if picked >= 2:
                break
            cleaned = _clean_preview(ch.get("content", ""))
            if cleaned:
                chunk_previews.append({"source": title, "text": cleaned})
                picked += 1

    # --- Journey: extraction + selection ------------------------------------------
    cib_ids = cib_data["driver_ids"]
    all_drivers = [{
        "id": d["id"], "name": d["name"], "origin": d.get("origin"),
        "dimension": d.get("dimension_type"), "selected": d["id"] in cib_ids,
    } for d in merge["unified_drivers"]]

    # --- Journey: manifestations (in morphbox order = optimistic → pessimistic) ---
    manif_order = morph["manifestations"].get(did, [])
    manif_by_id = {m["id"]: m for m in morph["all_manifestations"]}
    manifestations = [{
        "id": mid,
        "label": manif_by_id[mid].get("label", mid),
        "description": manif_by_id[mid].get("description", "")[:220],
        "plausibility": manif_by_id[mid].get("plausibility", "medium"),
    } for mid in manif_order if mid in manif_by_id]

    # --- Journey: couplings with the 5-persona panel votes ------------------------
    name_by_id = dict(zip(cib_data["driver_ids"], cib_data["driver_names"]))
    personas = [p.get("name", p.get("id", "?"))
                for p in cib_data.get("panel_metadata", {}).get("personas", [])]
    out_entries = {e["driver_b_id"]: e for e in cib_data["entries"] if e["driver_a_id"] == did}
    in_entries = {e["driver_a_id"]: e for e in cib_data["entries"] if e["driver_b_id"] == did}
    couplings = []
    for other in set(out_entries) | set(in_entries):
        eo, ei = out_entries.get(other), in_entries.get(other)
        if (eo and eo["impact_score"]) or (ei and ei["impact_score"]):
            couplings.append({
                "other_id": other,
                "other_name": name_by_id.get(other, other),
                "score_out": eo["impact_score"] if eo else 0,
                "score_in": ei["impact_score"] if ei else 0,
                "persona_scores": eo.get("persona_scores") if eo else None,
                "consensus": eo.get("consensus_level") if eo else None,
                "reasoning": (eo.get("reasoning", "") or "")[:400] if eo else "",
            })
    couplings.sort(key=lambda c: -abs(c["score_out"]))

    # --- Journey: how the driver's futures distribute over the 120 scenarios ------
    manif_idx = {mid: i for i, mid in enumerate(manif_order)}
    scenario_manif = {}
    for s in scen:
        for a in s.get("assumptions", []):
            if a.get("driver_id") == did:
                idx = manif_idx.get(a.get("manifestation_id"))
                if idx is not None:
                    scenario_manif[s["id"]] = idx
    dist_counts = [0] * len(manif_order)
    for idx in scenario_manif.values():
        dist_counts[idx] += 1
    distribution = [{"label": manifestations[i]["label"], "count": dist_counts[i]}
                    for i in range(len(manifestations))]

    # --- Journey: archetype stances (join via seed_id, ties flagged honestly) -----
    by_seed = {}
    for s in scen:
        by_seed.setdefault(s.get("seed_id"), s)
    stances = []
    for a in arch.get("archetypes", []):
        counts: dict[str, int] = {}
        for sid in a.get("member_scenario_ids", []):
            s = by_seed.get(sid)
            if not s:
                continue
            for asm in s.get("assumptions", []):
                if asm.get("driver_id") == did:
                    idx = manif_idx.get(asm.get("manifestation_id"))
                    if idx is not None:
                        lbl = manifestations[idx]["label"]
                        counts[lbl] = counts.get(lbl, 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: -kv[1])
        top_n = ordered[0][1] if ordered else 0
        tie = len([1 for _, n in ordered if n == top_n]) > 1
        stances.append({
            "archetype": a["label"], "size": a["size"],
            "top": ordered[0][0] if ordered and not tie else None,
            "top_count": top_n, "tie": tie, "counts": counts,
        })

    # --- Field (120 points incl. 3D) + lenses -------------------------------------
    points = [{
        "id": p["scenario_id"], "title": p.get("title", ""),
        "x": p.get("x"), "y": p.get("y"),
        "cx": p.get("cx"), "cy": p.get("cy"), "cz": p.get("cz"),
        # cluster-space coords (UMAP of the ordinal matrix HDBSCAN clustered)
        "ox": p.get("ox"), "oy": p.get("oy"),
        "ox3": p.get("ox3"), "oy3": p.get("oy3"), "oz3": p.get("oz3"),
        "archetype": p.get("archetype", "Continuum"),
        "is_representative": p.get("is_representative", False),
    } for p in land.get("points", [])]

    structure = land.get("structure", {})

    # Extraction-mechanism scene data (optional artifact — the deck must not die on it)
    try:
        extraction = load("present_extraction", kb)
    except FileNotFoundError:
        extraction = None

    # CIB inhibiting share measured LIVE from the persisted matrix — single source of truth
    # for the improvement lever, the validation chip and the coupling stat bar. (The old
    # hardcoded 22% was the historical fix-time measurement; the final run sits at 53/182.)
    cib_matrix = cib_data.get("matrix") or []
    cib_signs = [[(1 if v > 0 else -1 if v < 0 else 0) for v in row] for row in cib_matrix]
    offdiag = [v for i, row in enumerate(cib_matrix) for j, v in enumerate(row) if i != j]
    n_cib_pairs = len(offdiag)
    n_cib_inhibiting = sum(1 for v in offdiag if v < 0)
    cib_share = round(n_cib_inhibiting / n_cib_pairs, 3) if n_cib_pairs else 0.22

    return {
        "meta": {
            "sources": len(ov.get("sources", {})),
            "chunks": len(ov.get("chunks", {})),
            "drivers_total": len(merge["unified_drivers"]),
            "cib_drivers": len(cib_ids),
            "combinations": 268435456,
            "scenarios": len(scen),
            "archetypes": arch.get("n_archetypes", 5),
            "fixed_points": 510,
            "mc_samples": 2000,
        },
        "journey": {
            "driver": {
                "id": did, "name": driver["name"],
                "description": driver.get("description", "")[:300],
                "origin": driver.get("origin"), "confidence": driver.get("confidence"),
                "dimension": driver.get("dimension_type"),
                "axis_role": driver.get("axis_role"),
                "n_chunks": len(chunk_ids), "n_chunks_resolved": resolved,
                "n_sources": len(by_source),
                "top_sources": [{"title": t, "count": len(cs)} for t, cs in top_sources[:5]],
            },
            "chunk_previews": chunk_previews,
            "all_drivers": all_drivers,
            "manifestations": manifestations,
            "couplings": couplings,
            "personas": personas,
            "distribution": distribution,
            "scenario_manif": scenario_manif,
            "archetype_stances": stances,
        },
        "extraction": extraction,
        "field": {
            "points": points,
            "pc_shares_3d": structure.get("pc_shares_3d"),
        },
        "lenses": {
            "summary": structure.get("lenses", {}),
            "labels": structure.get("lens_labels", {}),
            "floor": structure.get("floor", 0.25),
        },
        "validation": validation,
        # Improvement levers: CIB share computed from the live matrix, the rest historically
        # measured (differentiation_fix_results.md).
        "improvement": {
            "cib_negative_share": {"before": 0.0, "after": cib_share,
                                   "band": [0.20, 0.30], "band_label": "Weimer-Jehle 20–30%"},
            "cib_matrix_signs": cib_signs,
            "cib_counts": {"pairs": n_cib_pairs, "inhibiting": n_cib_inhibiting},
            "z_score": {"before": 1.4, "after": 3.55, "significant_at": 2.0},
            "corpus_chunks": {"before": 2875, "after": 3905},
            "lens_progression": [
                {"name": "one-hot · k-means", "key": "onehot_kmeans", "silhouette": 0.074},
                {"name": "ordinal · k-means", "key": "ordinal_kmeans", "silhouette": 0.17},
                {"name": "one-hot · HDBSCAN", "key": "onehot_hdbscan", "silhouette": 0.3365},
                {"name": "ordinal · HDBSCAN", "key": "ordinal_hdbscan", "silhouette": 0.3799},
            ],
        },
        "parcoords": land.get("parcoords"),
    }


@app.get("/api/present")
async def present(kb: str = "spectrum"):
    mtime = os.path.getmtime(_resolve("landscape_state_combi", kb))
    if _present_cache["data"] is None or _present_cache["mtime"] != mtime:
        _present_cache["data"] = _build_present_bundle(kb)
        _present_cache["mtime"] = mtime
    return _present_cache["data"]


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
