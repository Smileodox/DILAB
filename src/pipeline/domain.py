"""Domain abstraction step: derive a DomainProfile from the docked knowledge base.

Runs FIRST in any pipeline. Samples the KB, asks the model to infer the domain framing
(domain, system, horizon, actor, competitors, forcing functions, calibration examples,
retrieval queries) plus a domain-specific expert panel, applies config overrides (hybrid:
derive then pin), and persists data/outputs/domain_profile.json. Downstream steps load it
via load_profile() and inject profile.prompt_kwargs() into otherwise neutral prompts.
"""
from __future__ import annotations

import json
import logging
import os

from src import config
from src.llm import safe_chat_json
from src.models.domain import DomainProfile, ForcingFunction, Persona
from src.prompts.domain import DOMAIN_PERSONAS, DOMAIN_PROFILE_EXTRACT

log = logging.getLogger(__name__)


def _sample_kb(collection, n: int = 50) -> tuple[str, list[str]]:
    """A broad, query-free sample of the KB (avoids the chicken-and-egg of needing a
    domain query to discover the domain)."""
    got = collection.get(limit=n, include=["documents", "metadatas"])
    ids = got.get("ids", []) or []
    docs = got.get("documents", []) or []
    metas = got.get("metadatas", []) or []
    parts = []
    for cid, doc, meta in zip(ids, docs, metas):
        title = (meta or {}).get("source_title", "?")
        parts.append(f"[Chunk ID: {cid}] (Source: {title})\n{(doc or '')[:800]}")
    return "\n\n---\n\n".join(parts), ids


def _as_text(v) -> str:
    """Coerce a free-text field to a string — the model often returns a list of bullets."""
    if isinstance(v, list):
        return "\n".join(f"- {x}" if not str(x).lstrip().startswith(("-", "•")) else str(x) for x in v)
    return str(v) if v is not None else ""


def _apply_overrides(profile: DomainProfile) -> DomainProfile:
    """Hybrid layer: config/env values pin the derived framing when set."""
    if config.DOMAIN_LABEL:
        profile.domain = config.DOMAIN_LABEL
    if config.DOMAIN_HORIZON:
        profile.horizon = config.DOMAIN_HORIZON
    if config.DOMAIN_ACTOR:
        profile.actor = config.DOMAIN_ACTOR
    return profile


def derive(collection, model: str | None = None, n_sample: int = 50) -> DomainProfile:
    model = model or config.DOMAIN_MODEL
    kb_sample, sample_ids = _sample_kb(collection, n_sample)
    if not kb_sample.strip():
        raise RuntimeError("KB sample is empty — is a knowledge base docked?")

    res = safe_chat_json(DOMAIN_PROFILE_EXTRACT.format(kb_sample=kb_sample), temperature=0.3, model=model)
    if not res.get("domain"):
        raise RuntimeError("Domain profiling failed — model returned no domain. Check KB/model.")

    forcing = [
        ForcingFunction(name=f.get("name", ""), description=f.get("description", ""))
        for f in res.get("forcing_functions", []) if isinstance(f, dict) and f.get("name")
    ]
    profile = DomainProfile(
        domain=res["domain"],
        domain_description=res.get("domain_description", ""),
        system=res.get("system", ""),
        horizon=str(res.get("horizon") or "2035"),
        actor=res.get("actor", ""),
        actor_role=res.get("actor_role", ""),
        competitors=[c for c in res.get("competitors", []) if isinstance(c, str)],
        forcing_functions=forcing,
        function_examples=_as_text(res.get("function_examples", "")),
        direction_good_example=_as_text(res.get("direction_good_example", "")),
        direction_bad_example=_as_text(res.get("direction_bad_example", "")),
        manifestation_example=_as_text(res.get("manifestation_example", "")),
        cib_inhibit_examples=_as_text(res.get("cib_inhibit_examples", "")),
        retrieval_queries={k: v for k, v in (res.get("retrieval_queries") or {}).items() if isinstance(v, str)},
        source_chunk_ids=res.get("source_chunk_ids_used") or sample_ids[:10],
    )

    pres = safe_chat_json(
        DOMAIN_PERSONAS.format(domain=profile.domain, domain_description=profile.domain_description),
        temperature=0.4, model=model,
    )
    profile.personas = [
        Persona(id=p["id"], name=p.get("name", p["id"]), system=p["system"], model=config.DOMAIN_MODEL)
        for p in pres.get("personas", []) if isinstance(p, dict) and p.get("id") and p.get("system")
    ]
    return _apply_overrides(profile)


def run(output_dir: str = "data/outputs", model: str | None = None, collection="auto",
        n_sample: int = 50) -> DomainProfile:
    if collection == "auto":
        from src.rag import get_collection
        collection = get_collection()

    print("[domain] deriving DomainProfile from the docked KB ...", flush=True)
    profile = derive(collection, model=model, n_sample=n_sample)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "domain_profile.json")
    with open(path, "w") as f:
        json.dump(profile.model_dump(mode="json"), f, indent=2)

    print(f"  domain: {profile.domain!r} | horizon {profile.horizon} | actor {profile.actor!r}")
    print(f"  {len(profile.personas)} personas, {len(profile.forcing_functions)} forcing functions, "
          f"{len(profile.competitors)} competitors")
    print(f"  → {path}")
    return profile


def load_profile(path: str | None = None) -> DomainProfile:
    """Load the persisted DomainProfile; raise a helpful error if the domain step never ran."""
    path = path or config.DOMAIN_PROFILE_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No domain profile at {path}. Run the domain step first "
            "(uv run python run_domain.py) so the pipeline knows which domain the KB is about."
        )
    with open(path) as f:
        return DomainProfile.model_validate(json.load(f))
