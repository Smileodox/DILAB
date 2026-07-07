"""SAO extraction, LLM causal explanations, and technology influence graph."""
from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# v3-base:free was removed on OpenRouter; try env override then working free models
DEFAULT_MODELS = [
    "deepseek/deepseek-v4-flash:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
    "openrouter/free",
]

_NLP = None
_last_llm_error: str | None = None


def _model_candidates() -> list[str]:
    env_model = os.getenv("OPENROUTER_MODEL", "").strip()
    if env_model:
        return [m.strip() for m in env_model.split(",") if m.strip()]
    legacy = os.getenv("OPENROUTER_LEGACY_MODEL", "deepseek/deepseek-v3-base:free")
    return [legacy] + [m for m in DEFAULT_MODELS if m != legacy]


def _get_nlp():
    global _NLP
    if _NLP is None:
        import spacy

        try:
            _NLP = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download

            download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm")
    return _NLP


def _extract_message_text(message: dict) -> str | None:
    content = message.get("content")
    if content and str(content).strip():
        return str(content).strip()
    reasoning = message.get("reasoning") or ""
    if reasoning:
        return _extract_from_reasoning(str(reasoning))
    return None


def _extract_from_reasoning(text: str) -> str:
    """Use final non-meta sentences when model returns reasoning-only output."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    skip = re.compile(r"^(okay|let me|wait|first|i remember|another thought|hmm)", re.I)
    usable = [s.strip() for s in sentences if s.strip() and len(s) > 25 and not skip.match(s)]
    if usable:
        return " ".join(usable[-3:])
    return text.strip()[-600:]


def llm_chat(system: str, user: str, max_tokens: int = 280) -> str:
    global _last_llm_error
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key == "your_openrouter_api_key_here":
        _last_llm_error = "missing_api_key"
        return _contextual_fallback(system, user)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:5001"),
        "X-Title": "Technology Foresight",
    }

    for model in _model_candidates():
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.35,
        }
        try:
            r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
            if r.status_code == 429:
                _last_llm_error = f"rate_limit:{model}"
                continue
            if r.status_code == 404:
                _last_llm_error = f"model_not_found:{model}"
                continue
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                _last_llm_error = str(data["error"])
                continue
            text = _extract_message_text(data["choices"][0].get("message", {}))
            if text and "corpus patterns" not in text[:30].lower():
                _last_llm_error = None
                return text
            _last_llm_error = f"empty_content:{model}"
        except Exception as exc:
            _last_llm_error = str(exc)
            logger.warning("OpenRouter call failed for %s: %s", model, exc)
            continue

    return _contextual_fallback(system, user)


def _contextual_fallback(system: str, user: str) -> str:
    """Data-driven explanation when API unavailable — never the old generic paragraph."""
    if "Event type:" in user or "event type:" in user.lower():
        return _fallback_event_explanation(user)
    if "Keywords:" in user and "lifecycle" in system.lower():
        return _fallback_lifecycle_explanation(user, system)
    if "Clusters:" in user:
        return (
            "Influence links were inferred from co-occurring topic themes and publication trends in your corpus. "
            "Enablement usually flows from foundational methods toward applied clusters; displacement appears when "
            "a rising topic's keywords overlap a declining one."
        )
    if "Driver A" in user or "Scenario:" in user:
        return _fallback_scenario_snippet(user)
    if "PATH 1" in user or "Core technology:" in user:
        return _fallback_impact_path_response(user)
    return _fallback_generic(user)


def _fallback_impact_path_response(user: str) -> str:
    """Structured fallback when LLM unavailable for impact-tree enrichment."""
    main = _field(user, "Core technology") or "the core technology"
    blocks = re.split(r"PATH\s+\d+", user)[1:]
    lines = []
    for i, block in enumerate(blocks, 1):
        evolving = _field(block, "Evolving technology") or _field(block, "Evolving/adjacent technology") or "adjacent tech"
        relation = _field(block, "Relation to core") or _field(block, "Relation") or "influences"
        signal = _field(block, "Corpus signal") or ""
        lines.append(f"PATH {i}")
        lines.append(
            f"BRANCH|{evolving} {relation} {main} based on corpus signals"
            f"{': ' + signal[:100] if signal else ''}."
        )
        lines.append(
            f"IMPACT|Innovation|Capability shift for {main}|"
            f"{evolving} is linked to {main} via {relation} in the research corpus.|"
            f"R&D teams integrate methods from {evolving} into {main} roadmaps and benchmarks."
        )
        lines.append(
            f"IMPACT|Economy|Market spillover|Growth or disruption around {evolving} reallocates investment near {main}.|"
            f"Funding, vendors, and customer demand shift along the shared value chain between both areas."
        )
    return "\n".join(lines)


def _fallback_event_explanation(user: str) -> str:
    ev_type = _field(user, "Event type") or "shift"
    year = _field(user, "Year") or "recent years"
    kws = _field(user, "Topic keywords") or _field(user, "Keywords") or "this technology area"
    prior = _field(user, "Corpus signal") or _field(user, "Prior context") or ""
    related = _field(user, "Related topic") or ""
    lifecycle = _field(user, "Lifecycle stage") or ""
    cluster = _field(user, "Cluster label") or kws

    causes = {
        "emerge": (
            f"In {year}, publications on «{cluster}» appeared as a distinct cluster—likely driven by a breakthrough paper, "
            f"open-source release, or funding call that made «{kws}» tractable at scale."
        ),
        "grow": (
            f"Volume for «{cluster}» rose in {year} because adjacent tooling matured and researchers consolidated on "
            f"«{kws}» after successful benchmarks—classic growth-phase adoption."
        ),
        "shift": (
            f"Keyword overlap with «{related or 'a neighboring topic'}» in {year} shows researchers reframing problems; "
            f"thematic shift often follows a dominant architecture change in «{kws}»."
        ),
        "merge": (
            f"«{cluster}» and «{related or 'another active topic'}» converged in {year}—shared methods and datasets "
            f"pull separate lines of work together."
        ),
        "die": (
            f"«{cluster}» faded by {year} as attention moved to successor approaches in «{kws}»—typical when a paradigm "
            f"is superseded or funding reallocates."
        ),
    }
    cause = causes.get(ev_type, causes["shift"])
    influence = ""
    if related:
        influence = f" A proximate cause is co-evolution with «{related}»."
    elif lifecycle:
        influence = f" The cluster sits in «{lifecycle}» on the fitted S-curve."
    prior_bit = f" Signal: {prior[:120]}." if prior else ""
    return (
        f"{cause}{influence} Over the next five years, expect consolidation around whichever sub-topic keeps "
        f"gaining citations in this corpus.{prior_bit}"
    )


def _fallback_lifecycle_explanation(user: str, system: str) -> str:
    kws = _field(user, "Keywords") or "this field"
    stage = "introduction"
    for s in ("introduction", "growth", "maturity", "decline"):
        if s in system.lower():
            stage = s
            break
    texts = {
        "introduction": (
            f"«{kws}» is in introduction: few papers but rising novelty—watch for hardware, datasets, or standards "
            f"that could trigger rapid growth."
        ),
        "growth": (
            f"«{kws}» is accelerating—publication counts climb as industry adopts proven results; competition shifts "
            f"from research novelty to scalability and cost."
        ),
        "maturity": (
            f"«{kws}» is maturing—incremental gains dominate; differentiation moves to integration, regulation, and "
            f"vertical applications."
        ),
        "decline": (
            f"«{kws}» is declining—research and investment migrate to successor technologies; incumbents should plan "
            f"migration or niche specialization."
        ),
    }
    return texts.get(stage, texts["growth"])


def _fallback_scenario_snippet(user: str) -> str:
    title = "This scenario"
    for name in ("Optimistic", "Disruptive", "Constrained", "Stagnant"):
        if name in user:
            title = f"The {name.lower()} scenario"
            break
    return (
        f"{title.capitalize()} follows the uncertainty drivers and dominant topic trends in your corpus—technologies "
        f"with rising publication share gain leverage, while constrained or stagnant futures assume slower adoption "
        f"or regulatory friction."
    )


def _fallback_generic(user: str) -> str:
    return (
        "This interpretation is derived from detected topic trends, lifecycle stages, and influence paths in your "
        f"uploaded corpus. Key themes: {user[:200]}."
    )


def _field(text: str, name: str) -> str:
    m = re.search(rf"{re.escape(name)}:\s*([^\n]+)", text, re.I)
    return m.group(1).strip() if m else ""


def extract_sao_triples(texts: list[str], topics: list[int]) -> dict[str, Any]:
    nlp = _get_nlp()
    by_topic: dict[int, list[dict]] = defaultdict(list)

    for text, tid in zip(texts, topics):
        doc = nlp(text[:4000])
        for sent in doc.sents:
            subj = verb = obj = None
            for tok in sent:
                if tok.dep_ in ("nsubj", "nsubjpass") and subj is None:
                    subj = tok.lemma_
                if tok.pos_ == "VERB" and verb is None:
                    verb = tok.lemma_
                if tok.dep_ in ("dobj", "pobj") and obj is None:
                    obj = tok.lemma_
            if subj and verb:
                by_topic[int(tid)].append({"subject": subj, "action": verb, "object": obj or ""})

    grouped = {}
    for tid, triples in by_topic.items():
        action_counts: dict[str, int] = defaultdict(int)
        rels = []
        for t in triples[:80]:
            action_counts[t["action"]] += 1
            rels.append(t)
        top_actions = sorted(action_counts.items(), key=lambda x: -x[1])[:5]
        grouped[str(tid)] = {
            "triples": rels[:25],
            "dominant_actions": [{"action": a, "count": c} for a, c in top_actions],
            "why": (
                "spaCy dependency parsing extracted Subject–Action–Object patterns from abstracts; "
                "dominant verbs summarize what each cluster *does* technologically."
            ),
        }
    return grouped


def _foresight_context_lines(foresight: dict[str, Any] | None) -> str:
    if not foresight:
        return ""
    label = foresight.get("topic_label", "").strip()
    year = foresight.get("horizon_year")
    parts = []
    if label:
        parts.append(f"Focus domain: {label}")
    if year:
        parts.append(f"Forecast horizon: {year}")
    return ("\n" + "\n".join(parts)) if parts else ""


def explain_change_events(
    events: list[dict],
    clusters: list[dict],
    influence: list[dict] | None = None,
    lifecycle: dict[str, Any] | None = None,
    foresight: dict[str, Any] | None = None,
) -> list[dict]:
    kw_map = {c["topic_id"]: c.get("keywords", []) for c in clusters}
    label_map = {c["topic_id"]: c.get("label", "") for c in clusters}
    lifecycle = lifecycle or {}
    influence = influence or []
    enriched = []

    for ev in events:
        tid = ev.get("topic_id")
        kws = ev.get("keywords") or kw_map.get(tid, [])
        kws_str = ", ".join(kws[:8])
        label = label_map.get(tid, kws_str)
        rel_tid = ev.get("related_topic")
        rel_label = label_map.get(rel_tid, f"Topic {rel_tid}") if rel_tid is not None else ""
        lc = lifecycle.get(str(tid), {})
        stage = lc.get("stage", "")

        inf_hint = ""
        for edge in influence[:6]:
            if label and (label in edge.get("from", "") or label in edge.get("to", "")):
                inf_hint = f"{edge.get('from')} —{edge.get('relation')}→ {edge.get('to')}: {edge.get('reason', '')[:80]}"

        horizon = foresight.get("horizon_year") if foresight else None
        impact_window = f"{horizon} horizon" if horizon else "next 5 years"
        system = (
            "You are a technology foresight analyst. Write 2-3 sentences ONLY.\n"
            "Structure: (1) ROOT CAUSE — why this event happened in the research corpus; "
            "(2) INFLUENCING TECHNOLOGY — name a specific adjacent tech or method; "
            f"(3) IMPACT — what this means for industry or R&D by the {impact_window}.\n"
            "Be specific to the keywords and event type. Stay in the user's focus domain. "
            "Do NOT default to telecommunications unless the corpus is telecom."
        )
        user = (
            f"Event type: {ev.get('type')}\n"
            f"Year: {ev.get('year')}\n"
            f"Cluster label: {label}\n"
            f"Topic keywords: {kws_str}\n"
            f"Lifecycle stage: {stage}\n"
            f"Related topic: {rel_label}\n"
            f"Corpus signal: {ev.get('why', '')}\n"
            f"Influence context: {inf_hint or 'none listed'}"
            f"{_foresight_context_lines(foresight)}"
        )
        explanation = llm_chat(system, user, max_tokens=260)
        enriched.append(
            {
                **ev,
                "llm_explanation": explanation,
                "llm_source": "openrouter" if _last_llm_error is None else "contextual_fallback",
            }
        )
    return enriched


def build_influence_graph(
    clusters: list[dict],
    documents: list[dict],
    foresight: dict[str, Any] | None = None,
) -> list[dict]:
    edges = []
    labels = [c.get("label", f"Topic {c['topic_id']}") for c in clusters[:8]]
    if len(labels) < 2:
        return edges

    kw_lines = [
        f"{c.get('label')}: {', '.join((c.get('keywords') or [])[:5])}" for c in clusters[:8]
    ]
    system = (
        "You are a technology foresight analyst. List technology influence pairs grounded in the clusters.\n"
        "Format each line: ENABLE|TechA|TechB|specific reason   OR   DISPLACE|TechA|TechB|specific reason\n"
        "Up to 8 lines. Reasons must mention methods, dependencies, or market dynamics—not generic text. "
        "Use only technologies present in the clusters; do not invent a telecommunications focus."
    )
    user = "Topic clusters:\n" + "\n".join(kw_lines) + _foresight_context_lines(foresight)
    raw = llm_chat(system, user, max_tokens=320)

    for line in raw.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[0].upper() in ("ENABLE", "DISPLACE"):
            edges.append(
                {
                    "from": parts[1],
                    "to": parts[2],
                    "relation": "enables" if parts[0].upper() == "ENABLE" else "displaces",
                    "reason": parts[3],
                    "why": "LLM inferred enablement/displacement from cluster themes and publication dynamics.",
                }
            )

    if len(edges) < 2:
        for i in range(min(2, len(labels) - 1)):
            edges.append(
                {
                    "from": labels[i],
                    "to": labels[i + 1],
                    "relation": "enables",
                    "reason": f"Shared methods between «{labels[i]}» and «{labels[i + 1]}» in the corpus.",
                    "why": "Heuristic edge when LLM output was sparse.",
                }
            )
    return edges[:12]


def lifecycle_llm_blurb(stage: str, keywords: list[str], label: str = "") -> str:
    kws = ", ".join(keywords[:8])
    system = (
        f"You are a technology foresight analyst. Explain what the «{stage}» lifecycle stage means "
        f"for this specific technology area in 2-3 sentences. Mention drivers (adoption, funding, standards) "
        f"relevant to the keywords. No generic filler."
    )
    user = f"Technology: {label or kws}\nKeywords: {kws}\nLifecycle stage: {stage}"
    return llm_chat(system, user, max_tokens=200)
