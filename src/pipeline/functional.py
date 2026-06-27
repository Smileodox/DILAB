"""Functional morphological analysis (Zwicky) — alternative driver model.

Drivers = technical FUNCTIONS; manifestations = COMPETING DIRECTIONS (paradigms);
consistency = Cross-Consistency Assessment (CCA) over direction pairs. This is the proper
Zwicky method and the fix for the structureless cloud the BOM/optimism-ladder path produces.
Coexists with the BOM/CIB path (writes *_zwicky / cca files).

Flow: extract functions (KB) -> per function extract competing directions (KB) -> morphbox
      -> CCA over cross-function direction pairs -> sample CCA-consistent configurations.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import config
from src.llm import safe_chat_json
from src.models.common import _id
from src.models.domain import DomainProfile
from src.models.drivers import DriverConfidence, DriverOrigin, TechDriver
from src.models.morphological import (
    ConsistencyResult,
    DriverManifestation,
    MorphologicalBox,
)
from src.prompts.functional import (
    CCA_FUNCTION_PAIR,
    CCA_FUNCTION_PAIR_CONTRASTIVE,
    DIRECTIONS_EXTRACT,
    FUNCTION_EXTRACT,
)

log = logging.getLogger(__name__)

# Used when a step is called without a profile (e.g. unit tests) — generic fallbacks only.
_NEUTRAL = DomainProfile(domain="this technology domain")


def _rag_text(collection, query: str, n: int = 5) -> str:
    if collection is None:
        return ""
    try:
        from src.rag import format_rag_chunks, retrieve

        return format_rag_chunks(retrieve(collection, query, pool="trend", n=n))
    except Exception as e:  # noqa: BLE001 — grounding is best-effort
        log.warning("RAG retrieve failed (%s) — continuing without grounding", e)
        return ""


# --- extraction ----------------------------------------------------------------------

def extract_functions(collection=None, model: str | None = None,
                      profile: DomainProfile | None = None) -> list[dict]:
    profile = profile or _NEUTRAL
    rag = _rag_text(
        collection,
        profile.query("functions",
                      f"{profile.domain} technical functions core capabilities building blocks"),
        n=6,
    )
    res = safe_chat_json(FUNCTION_EXTRACT.format(rag_chunks=rag, **profile.prompt_kwargs()),
                         temperature=0.4, model=model)
    out = []
    for f in res.get("functions", []):
        if f.get("name"):
            out.append({"id": _id(), "name": f["name"], "description": f.get("description", "")})
    return out


def extract_directions(function: dict, collection=None, model: str | None = None,
                       profile: DomainProfile | None = None) -> list[DriverManifestation]:
    profile = profile or _NEUTRAL
    rag = _rag_text(
        collection,
        profile.query("directions",
                      f"{function['name']} {function['description']} competing approaches "
                      f"paradigms architectures alternatives"),
        n=5,
    )
    res = safe_chat_json(
        DIRECTIONS_EXTRACT.format(
            function_name=function["name"],
            function_description=function["description"],
            rag_chunks=rag,
            **profile.prompt_kwargs(),
        ),
        temperature=0.5, model=model,
    )
    manifs = []
    for d in res.get("directions", []):
        if not d.get("label"):
            continue
        plaus = d.get("plausibility", "medium")
        manifs.append(DriverManifestation(
            driver_id=function["id"],
            label=d["label"],
            description=d.get("description", ""),
            plausibility=plaus if plaus in ("high", "medium", "low") else "medium",
            source_chunk_ids=res.get("source_chunk_ids_used", []),
        ))
    return manifs


def build_morphbox(collection=None, model: str | None = None, max_workers: int = 6,
                   profile: DomainProfile | None = None):
    profile = profile or _NEUTRAL
    functions = extract_functions(collection, model, profile)
    log.info("Extracted %d candidate functions", len(functions))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(extract_directions, f, collection, model, profile): f for f in functions}
        directions = {futs[fut]["id"]: fut.result() for fut in as_completed(futs)}

    # A function is only a real morphological dimension if it has >=2 competing directions.
    manifestations, all_manifs, kept = {}, [], []
    for f in functions:
        ms = directions.get(f["id"], [])
        if len(ms) >= 2:
            manifestations[f["id"]] = [m.id for m in ms]
            all_manifs.extend(ms)
            kept.append(f)

    morph = MorphologicalBox(
        drivers=[f["id"] for f in kept], manifestations=manifestations, all_manifestations=all_manifs,
    )
    tech_drivers = [
        TechDriver(id=f["id"], name=f["name"], description=f["description"],
                   origin=DriverOrigin.TREND, confidence=DriverConfidence.HIGH)
        for f in kept
    ]
    return morph, tech_drivers


# --- Cross-Consistency Assessment ----------------------------------------------------

CCA_PROMPTS = {"absolute": CCA_FUNCTION_PAIR, "contrastive": CCA_FUNCTION_PAIR_CONTRASTIVE}


def assess_cca(morph: MorphologicalBox, manif_by_id: dict, name_by_fid: dict,
               model: str | None = None, max_workers: int = 6,
               mode: str = "absolute", profile: DomainProfile | None = None) -> dict:
    """Score every cross-function direction pair for technical compatibility (-2..+2).

    ``mode="absolute"`` (default) uses the plain compatibility prompt. ``mode="contrastive"``
    flips the prior toward architectural tension and forces the per-pair scores to spread —
    the fix for the LLM positivity bias that leaves the absolute CCA matrix nearly all-positive
    (and the sampled field statistically indistinguishable from uniform random).
    """
    prompt_template = CCA_PROMPTS.get(mode, CCA_FUNCTION_PAIR)
    pkw = (profile or _NEUTRAL).prompt_kwargs()
    fids = morph.drivers
    cca: dict[str, dict[str, int]] = {}

    def _set(a, b, s):
        cca.setdefault(a, {})[b] = s
        cca.setdefault(b, {})[a] = s

    def _eval(fi: int, fj: int):
        fa, fb = fids[fi], fids[fj]
        ma = [manif_by_id[m] for m in morph.manifestations[fa]]
        mb = [manif_by_id[m] for m in morph.manifestations[fb]]
        block = lambda ms: "\n".join(f"  {k}. {m.label}: {m.description[:140]}" for k, m in enumerate(ms))
        res = safe_chat_json(
            prompt_template.format(
                function_a_name=name_by_fid[fa], function_b_name=name_by_fid[fb],
                directions_a=block(ma), directions_b=block(mb), **pkw,
            ),
            temperature=0.2, model=model,
        )
        out = []
        for p in res.get("pairs", []):
            ai, bi, s = p.get("a"), p.get("b"), p.get("score")
            if isinstance(ai, int) and isinstance(bi, int) and 0 <= ai < len(ma) and 0 <= bi < len(mb) \
                    and isinstance(s, (int, float)):
                out.append((ma[ai].id, mb[bi].id, int(max(-2, min(2, round(s))))))
        return out

    pairs = list(itertools.combinations(range(len(fids)), 2))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for fut in as_completed([pool.submit(_eval, fi, fj) for fi, fj in pairs]):
            for a, b, s in fut.result():
                _set(a, b, s)
    return cca


# --- CCA-based consistency + sampling ------------------------------------------------

def cca_contradiction(config_map: dict, morph: MorphologicalBox, cca: dict):
    """Return (contradiction_ratio in [0,1], hard_incompatible flag, net_compat)."""
    manifs = [config_map[d] for d in morph.drivers]
    n_pairs = neg = net = 0
    hard = False
    for a, b in itertools.combinations(manifs, 2):
        s = cca.get(a, {}).get(b, 0)
        n_pairs += 1
        net += s
        if s <= -2:
            hard = True
        if s < 0:
            neg += -s
    ratio = neg / (n_pairs * 2) if n_pairs else 0.0
    return ratio, hard, net


def sample_consistent(morph: MorphologicalBox, cca: dict, n_samples: int,
                      oversample_factor: float = 5.0, reject_threshold: float = 0.25,
                      seed: int | None = None) -> list[ConsistencyResult]:
    """Sample configs, dropping hard-incompatible ones and those above the tension threshold."""
    rng = random.Random(seed)
    n_draw = max(n_samples, int(n_samples * oversample_factor))
    seen, kept = set(), []
    drawn = rejected = 0
    for _ in range(n_draw):
        if len(kept) >= n_samples:
            break
        cfg = {d: rng.choice(morph.manifestations[d]) for d in morph.drivers}
        key = tuple(cfg[d] for d in morph.drivers)
        if key in seen:
            continue
        seen.add(key)
        drawn += 1
        ratio, hard, net = cca_contradiction(cfg, morph, cca)
        if hard or ratio > reject_threshold:
            rejected += 1
            continue
        kept.append(ConsistencyResult(
            configuration=dict(cfg), consistency_score=float(net), is_consistent=True,
            contradiction_ratio=round(ratio, 4), scenario_type="", is_fixed_point=False, frequency=1,
        ))
    kept.sort(key=lambda r: (r.contradiction_ratio, -r.consistency_score))
    log.info("CCA sampling: kept %d/%d (drew %d unique, rejected %d at threshold %.2f)",
             len(kept), n_samples, drawn, rejected, reject_threshold)
    return kept


# --- orchestration -------------------------------------------------------------------

def run(output_dir: str = "data/outputs", n_samples: int | None = None,
        reject_threshold: float = 0.25, model: str | None = None, collection="auto",
        max_workers: int = 6, seed: int | None = None, cca_mode: str = "contrastive",
        profile: DomainProfile | None = None) -> dict:
    n_samples = config.COMBI_N_SAMPLES if n_samples is None else n_samples
    seed = config.COMBI_SEED if seed is None else seed
    if profile is None:
        from src.pipeline.domain import load_profile
        profile = load_profile()
    if collection == "auto":
        try:
            from src.rag import get_collection
            collection = get_collection()
        except Exception as e:  # noqa: BLE001
            log.warning("No KB collection (%s) — extracting without RAG grounding", e)
            collection = None

    def p(name):
        return os.path.join(output_dir, name)

    print(f"[1/4] Extracting functions + competing directions (domain: {profile.domain!r}) ...", flush=True)
    morph, tech_drivers = build_morphbox(collection, model, max_workers, profile)
    name_by_fid = {d.id: d.name for d in tech_drivers}
    manif_by_id = {m.id: m for m in morph.all_manifestations}
    print(f"  {len(morph.drivers)} functions, {len(morph.all_manifestations)} directions", flush=True)
    if len(morph.drivers) < 3:
        raise RuntimeError("Too few functional drivers extracted; check KB/model.")

    json.dump({"drivers": morph.drivers, "manifestations": morph.manifestations,
               "all_manifestations": [m.model_dump(mode="json") for m in morph.all_manifestations]},
              open(p("morphbox_zwicky_state.json"), "w"), indent=2)
    json.dump({"unified_drivers": [d.model_dump(mode="json") for d in tech_drivers]},
              open(p("functional_merge_state.json"), "w"), indent=2)

    print(f"[2/4] Cross-Consistency Assessment (CCA, mode={cca_mode}) ...", flush=True)
    cca = assess_cca(morph, manif_by_id, name_by_fid, model, max_workers, mode=cca_mode, profile=profile)
    json.dump({"cca": cca, "n_functions": len(morph.drivers), "cca_mode": cca_mode},
              open(p("cca_state.json"), "w"), indent=2)
    scores = [s for d in cca.values() for s in d.values()]
    if scores:
        nneg = sum(1 for s in scores if s < 0) // 2
        nhard = sum(1 for s in scores if s <= -2) // 2
        print(f"  scored {len(scores)//2} direction-pairs | negative {nneg} | hard(-2) {nhard} "
              f"| mean {sum(scores)/len(scores):+.2f}", flush=True)

    # Zero driver-CIB shim so scenario_gen yields empty cross-impact context for this path.
    nfn = len(morph.drivers)
    json.dump({"matrix": [[0] * nfn for _ in range(nfn)], "driver_ids": morph.drivers},
              open(p("cib_state_zwicky.json"), "w"), indent=2)

    print("[3/4] Sampling CCA-consistent configurations ...", flush=True)
    configs = sample_consistent(morph, cca, n_samples, reject_threshold=reject_threshold, seed=seed)
    json.dump({"configs": [c.model_dump(mode="json") for c in configs],
               "method": "functional_zwicky", "n_combinations": len(configs)},
              open(p("combinatorial_state_zwicky.json"), "w"), indent=2)

    print(f"[4/4] Done: {len(configs)} configs → {p('combinatorial_state_zwicky.json')}", flush=True)
    return {"morphbox": p("morphbox_zwicky_state.json"),
            "n_functions": len(morph.drivers), "n_configs": len(configs)}
