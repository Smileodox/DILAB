"""Discover technology impact paths from corpus signals for scenario-specific trees."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pipeline.reasoning import _last_llm_error, llm_chat

TREND_FROM_LIFECYCLE = {
    "introduction": "emerging",
    "growth": "accelerating",
    "maturity": "maturing",
    "decline": "declining",
}

# Which path types matter most per scenario quadrant
SCENARIO_PATH_PRIORITY = {
    "optimistic": {"grow", "emerge", "enables", "weak_signal", "cluster", "growth", "introduction", "accelerating"},
    "disruptive": {"die", "displaces", "shift", "merge", "disrupting", "declining", "decline"},
    "constrained": {"shift", "maturity", "maturing", "cluster", "enables"},
    "stagnant": {"die", "decline", "declining", "displaces", "shift", "stagnant"},
}

EVENT_TREND = {
    "emerge": "emerging",
    "grow": "accelerating",
    "shift": "shifting",
    "merge": "converging",
    "die": "declining",
}


def _make_impact(
    name: str,
    sector: str,
    why: str,
    how: str,
    *,
    evolving: str = "",
    main: str = "",
) -> dict[str, Any]:
    """Structured sector impact: why the link exists and how it materialises."""
    return {
        "name": name,
        "node_type": "impact",
        "sector": sector,
        "why": why,
        "how": how,
        "evolving_tech": evolving,
        "main_tech": main,
    }


def _cluster_lookup(clusters: list[dict]) -> dict[int, dict]:
    return {int(c["topic_id"]): c for c in clusters if c.get("topic_id") is not None}


def _label_for_topic(clusters: list[dict], topic_id: int | None) -> str:
    if topic_id is None:
        return "Adjacent technology"
    c = _cluster_lookup(clusters).get(int(topic_id))
    if not c:
        return f"Topic {topic_id}"
    return c.get("label") or ", ".join((c.get("keywords") or [])[:3])


def _main_matches(name: str, main_label: str) -> bool:
    a, b = name.strip().lower(), main_label.strip().lower()
    return a == b or a in b or b in a


def discover_impact_paths(
    main: dict[str, Any],
    clusters: list[dict],
    lifecycle: dict[str, Any],
    timeline: dict[str, list[dict]],
    events: list[dict],
    influence: list[dict],
    weak_signals: list[dict],
) -> list[dict[str, Any]]:
    """Collect all forecast paths: evolving tech → impacts on main technology."""
    main_label = main["label"]
    main_tid = main.get("topic_id")
    paths: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def add_path(
        evolving: str,
        source: str,
        trend: str,
        relation: str,
        why_path: str,
        impacts: list[dict[str, Any]],
        weight: float = 1.0,
        meta: dict | None = None,
    ) -> None:
        if _main_matches(evolving, main_label):
            return
        key = f"{evolving.lower()}|{source}|{relation}"
        if key in seen_keys and source != "event":
            return
        seen_keys.add(key)
        paths.append(
            {
                "evolving": evolving,
                "source": source,
                "trend": trend,
                "relation": relation,
                "why_path": why_path,
                "impacts": impacts,
                "weight": weight,
                "meta": meta or {},
            }
        )

    # Path type 1: influence graph edges touching main technology
    for edge in influence:
        fr, to, rel = edge.get("from", ""), edge.get("to", ""), edge.get("relation", "enables")
        reason = edge.get("reason", "")
        if _main_matches(to, main_label):
            evolving = fr
            trend = "accelerating" if rel == "enables" else "disrupting"
            add_path(
                evolving,
                "influence",
                trend,
                rel,
                reason or f"Influence graph: {evolving} {rel} {main_label}.",
                _impacts_from_relation(main_label, evolving, rel, trend, "influence"),
                weight=2.0,
                meta={"edge": edge},
            )
        elif _main_matches(fr, main_label):
            evolving = to
            trend = "accelerating" if rel == "enables" else "disrupting"
            add_path(
                evolving,
                "influence",
                trend,
                rel,
                reason or f"{main_label} {rel} {evolving}; downstream effects flow back via dependency.",
                _impacts_from_relation(main_label, evolving, rel, trend, "influence"),
                weight=1.8,
                meta={"edge": edge},
            )

    # Path type 2: temporal change events (each event = its own path)
    for ev in events:
        tid = ev.get("topic_id")
        rel_tid = ev.get("related_topic")
        ev_type = ev.get("type", "shift")
        if tid == main_tid and rel_tid is not None:
            evolving = _label_for_topic(clusters, rel_tid)
        elif tid != main_tid:
            evolving = _label_for_topic(clusters, tid)
        else:
            evolving = ", ".join((ev.get("keywords") or [])[:2]) or "Related topic"
        trend = EVENT_TREND.get(ev_type, "evolving")
        add_path(
            evolving,
            "event",
            trend,
            ev_type,
            ev.get("why", f"Detected {ev_type} event in corpus timeline."),
            _impacts_from_event(main_label, evolving, ev_type, ev),
            weight=1.5 + (0.3 if ev_type in ("emerge", "die") else 0),
            meta={"event": ev},
        )

    # Path type 3: other topic clusters (lifecycle-driven paths)
    for c in clusters:
        tid = c.get("topic_id")
        if tid == main_tid:
            continue
        label = c.get("label") or ", ".join((c.get("keywords") or [])[:3])
        lc = lifecycle.get(str(tid), {})
        stage = lc.get("stage") or c.get("lifecycle_stage", "growth")
        trend = TREND_FROM_LIFECYCLE.get(stage, "evolving")
        series = timeline.get(str(tid), [])
        vol_hint = ""
        if len(series) >= 2:
            vol_hint = f" Volume {series[0]['count']}→{series[-1]['count']} ({series[0]['year']}–{series[-1]['year']})."
        add_path(
            label,
            "cluster",
            trend,
            stage,
            f"Separate topic cluster at {stage} lifecycle.{vol_hint}",
            _impacts_from_lifecycle(main_label, label, stage, trend),
            weight=1.0 + min(1.0, len(series) / 5),
            meta={"topic_id": tid, "stage": stage},
        )

    # Path type 4: weak signals (each signal = path)
    for sig in weak_signals:
        lbl = sig.get("label") or _label_for_topic(clusters, sig.get("topic_id"))
        add_path(
            lbl,
            "weak_signal",
            "emerging (weak signal)",
            "emerge",
            sig.get("why", "Small cluster with rapid growth—potential breakthrough path."),
            _impacts_from_event(main_label, lbl, "emerge", sig),
            weight=1.4,
            meta={"weak_signal": sig},
        )

    return sorted(paths, key=lambda p: -p["weight"])


def select_paths_for_scenario(paths: list[dict[str, Any]], scenario_key: str) -> list[dict[str, Any]]:
    """Pick and rank paths so each scenario tree reflects a different forecast lens."""
    priorities = SCENARIO_PATH_PRIORITY.get(scenario_key, set())
    scored = []
    for p in paths:
        score = p["weight"]
        rel = p.get("relation", "")
        src = p.get("source", "")
        if src in priorities:
            score += 2.0
        if rel in priorities:
            score += 1.5
        if scenario_key == "optimistic" and p.get("relation") == "enables":
            score += 2.5
        if scenario_key == "disruptive" and p.get("relation") in ("displaces", "die"):
            score += 2.5
        if scenario_key == "stagnant" and "declin" in p.get("trend", ""):
            score += 2.0
        if scenario_key == "constrained" and p.get("relation") in ("shift", "maturity"):
            score += 1.8
        scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    # Include all paths above threshold; at least 1, no fixed max of 2
    if not scored:
        return []
    top_score = scored[0][0]
    selected = [p for s, p in scored if s >= top_score * 0.45]
    return selected if selected else [scored[0][1]]


def merge_paths_into_branches(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge paths that share the same evolving technology; combine impact leaves."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for p in paths:
        grouped[p["evolving"]].append(p)

    branches = []
    for evolving, group in grouped.items():
        impacts: list[dict] = []
        seen_impact: set[str] = set()
        sources = []
        trends = []
        whys = []
        for p in group:
            sources.append(p["source"])
            trends.append(p["trend"])
            whys.append(p.get("branch_why") or p["why_path"])
            for imp in p["impacts"]:
                key = imp["name"].lower()
                if key not in seen_impact:
                    seen_impact.add(key)
                    impacts.append(imp)

        branches.append(
            {
                "name": evolving,
                "node_type": "evolving",
                "trend": trends[0] if len(set(trends)) == 1 else " / ".join(sorted(set(trends))[:3]),
                "path_sources": sorted(set(sources)),
                "path_count": len(group),
                "why": " ".join(whys[:2]) if len(whys) <= 2 else f"{whys[0]} (+{len(group)-1} corroborating paths from corpus).",
                "children": impacts,
            }
        )
    return branches


def enrich_scenario_paths_with_llm(
    paths: list[dict[str, Any]],
    main: dict[str, Any],
    scenario_title: str,
    scenario_narrative: str = "",
    foresight: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Replace template impact rationales with LLM-generated sector impacts per path."""
    if not paths:
        return paths

    main_label = main["label"]
    blocks = []
    for i, p in enumerate(paths, 1):
        meta = p.get("meta") or {}
        extra = ""
        if ev := meta.get("event"):
            extra = (
                f"Event type: {ev.get('type', '')}\n"
                f"Event year: {ev.get('year', '')}\n"
                f"Event explanation: {ev.get('llm_explanation', ev.get('why', ''))}\n"
            )
        if edge := meta.get("edge"):
            extra += f"Influence edge reason: {edge.get('reason', '')}\n"
        blocks.append(
            f"PATH {i}\n"
            f"Evolving technology: {p['evolving']}\n"
            f"Relation to core: {p.get('relation', '')}\n"
            f"Trend: {p.get('trend', '')}\n"
            f"Corpus source: {p.get('source', '')}\n"
            f"Corpus signal: {p.get('why_path', '')}\n"
            f"{extra}".rstrip()
        )

    focus = (foresight or {}).get("topic_label", "").strip()
    horizon = (foresight or {}).get("horizon_year")
    horizon_line = f"Forecast horizon: {horizon}\n" if horizon else "Forecast horizon: next 5–10 years\n"

    system = (
        "You are a technology foresight analyst. For each PATH block, explain how the evolving "
        "technology affects the core technology in this scenario.\n"
        "Output format — repeat for every PATH:\n"
        "PATH N\n"
        "BRANCH|Why this evolving technology matters for the core technology (1-2 specific sentences)\n"
        "IMPACT|Sector|Short impact title|Why this sector is affected (1 sentence)|How the effect materialises (1 sentence)\n"
        "Rules:\n"
        "- Sector must be exactly one of: Economy, Society, Governance, Innovation\n"
        "- Provide 1-2 IMPACT lines per PATH\n"
        "- Name the actual technologies from the user's focus domain; no vague filler\n"
        "- Do NOT default to telecommunications unless the focus domain is telecommunications\n"
        "- Ground claims in the corpus signal, focus domain, and forecast horizon"
    )
    user = (
        f"Scenario: {scenario_title}\n"
        f"Focus domain: {focus or main_label}\n"
        f"{horizon_line}"
        f"Scenario narrative: {scenario_narrative or 'not provided'}\n"
        f"Core technology: {main_label}\n"
        f"Core keywords: {', '.join((main.get('keywords') or [])[:6])}\n\n"
        + "\n\n".join(blocks)
    )

    raw = llm_chat(system, user, max_tokens=900)
    parsed = _parse_scenario_impact_response(raw, len(paths))
    llm_ok = _last_llm_error is None and bool(parsed)

    enriched = []
    for i, p in enumerate(paths):
        entry = parsed.get(i + 1, {})
        impacts = entry.get("impacts") or []
        if impacts:
            for imp in impacts:
                imp["evolving_tech"] = p["evolving"]
                imp["main_tech"] = main_label
                imp["llm_source"] = "openrouter" if llm_ok else "contextual_fallback"
            branch_why = entry.get("branch_why") or p.get("why_path", "")
            enriched.append({**p, "impacts": impacts, "branch_why": branch_why, "llm_enriched": True})
        else:
            enriched.append(_fallback_path_impacts(p, main_label))
    return enriched


def _parse_scenario_impact_response(raw: str, path_count: int) -> dict[int, dict]:
    """Parse PATH N / BRANCH| / IMPACT| blocks from LLM output."""
    result: dict[int, dict] = {i: {"branch_why": "", "impacts": []} for i in range(1, path_count + 1)}
    current = 1

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"PATH\s+(\d+)", line, re.I)
        if m:
            current = min(int(m.group(1)), path_count)
            continue
        if line.upper().startswith("BRANCH|"):
            result[current]["branch_why"] = line.split("|", 1)[1].strip()
            continue
        if line.upper().startswith("IMPACT|"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                sector = _normalise_sector(parts[1])
                result[current]["impacts"].append(
                    _make_impact(
                        parts[2],
                        sector,
                        parts[3],
                        parts[4],
                    )
                )

    return {k: v for k, v in result.items() if v["impacts"] or v["branch_why"]}


def _normalise_sector(sector: str) -> str:
    s = sector.strip().lower()
    for label in ("Economy", "Society", "Governance", "Innovation"):
        if label.lower() in s:
            return label
    return "Innovation"


def _fallback_path_impacts(path: dict[str, Any], main_label: str) -> dict[str, Any]:
    """Template impacts when LLM output is missing or unparsable."""
    evolving = path["evolving"]
    source = path.get("source", "")
    relation = path.get("relation", "")
    trend = path.get("trend", "")
    meta = path.get("meta") or {}

    if source == "influence":
        impacts = _impacts_from_relation(main_label, evolving, relation, trend, source)
    elif source == "event":
        ev = meta.get("event", {})
        impacts = _impacts_from_event(main_label, evolving, relation, ev)
    elif source == "weak_signal":
        impacts = _impacts_from_event(main_label, evolving, "emerge", meta.get("weak_signal", {}))
    else:
        stage = meta.get("stage", relation)
        impacts = _impacts_from_lifecycle(main_label, evolving, stage, trend)

    for imp in impacts:
        imp["llm_source"] = "template_fallback"
    return {**path, "impacts": impacts, "branch_why": path.get("why_path", ""), "llm_enriched": False}


def build_tree_from_paths(
    main: dict[str, Any],
    paths: list[dict[str, Any]],
    scenario_title: str,
    scenario_key: str,
) -> dict[str, Any]:
    branches = merge_paths_into_branches(paths)
    return {
        "name": main["label"],
        "node_type": "main",
        "why": (
            f"{scenario_title} forecast for {main['label']}: {len(branches)} impact path(s) "
            f"discovered from influence edges, change events, clusters, and weak signals."
        ),
        "path_count": len(paths),
        "branch_count": len(branches),
        "scenario": scenario_key,
        "children": branches,
    }


def _impacts_from_relation(
    main: str,
    evolving: str,
    relation: str,
    trend: str,
    source: str,
) -> list[dict]:
    impacts = []
    if relation == "displaces" or "disrupt" in trend:
        impacts.extend(
            [
                _make_impact(
                    f"Substitution risk for {main}",
                    "Economy",
                    why=f"{evolving} is {trend} and competes for the same use cases as {main} in the corpus.",
                    how=f"Customers and R&D investment shift toward {evolving}, reducing spend on {main} deployments.",
                    evolving=evolving,
                    main=main,
                ),
                _make_impact(
                    "Standards fragmentation",
                    "Governance",
                    why=f"Rival technical stacks around {evolving} challenge the dominant design of {main}.",
                    how=f"Competing standards and interfaces force {main} vendors to support multiple ecosystems or lose interoperability.",
                    evolving=evolving,
                    main=main,
                ),
            ]
        )
    else:
        impacts.extend(
            [
                _make_impact(
                    f"Capability uplift for {main}",
                    "Innovation",
                    why=f"Corpus influence links show {evolving} {relation}s {main}—the technologies reinforce each other.",
                    how=f"Shared models, tooling, and research from {evolving} accelerate feature delivery and performance of {main}.",
                    evolving=evolving,
                    main=main,
                ),
                _make_impact(
                    "Talent & vendor spillover",
                    "Society",
                    why=f"Growth in {evolving} builds a skilled workforce and supplier base adjacent to {main}.",
                    how=f"Engineers and vendors trained on {evolving} lower hiring cost and integration friction when adopting {main}.",
                    evolving=evolving,
                    main=main,
                ),
            ]
        )
    if source == "influence" and len(impacts) < 3:
        impacts.append(
            _make_impact(
                f"Integration pathway via {evolving}",
                "Innovation",
                why=f"Direct {relation} relationship detected between {evolving} and {main} in the influence graph.",
                how=f"Product roadmaps can bundle {evolving} components into {main} offerings via APIs, SDKs, or co-developed modules.",
                evolving=evolving,
                main=main,
            )
        )
    return impacts


def _impacts_from_event(main: str, evolving: str, ev_type: str, ev: dict) -> list[dict]:
    year = ev.get("year", "")
    if ev_type == "emerge":
        return [
            _make_impact(
                f"New competitive surface for {main}",
                "Economy",
                why=f"{evolving} first appeared in the corpus ({year}), signalling a new market entrant near {main}.",
                how=f"Early movers in {evolving} can capture niches and set benchmarks before {main} incumbents respond.",
                evolving=evolving,
                main=main,
            ),
            _make_impact(
                "Partnership / acquisition target",
                "Economy",
                why=f"Emergence of {evolving} creates strategic options for firms invested in {main}.",
                how=f"Acquirers bundle {evolving} IP and teams into {main} platforms to secure first-mover advantage.",
                evolving=evolving,
                main=main,
            ),
        ]
    if ev_type == "grow":
        return [
            _make_impact(
                f"Demand pull for {main}",
                "Economy",
                why=f"Publication volume on {evolving} rose sharply ({year}), indicating rising market interest.",
                how=f"Increased funding and customer demand for {evolving} spills over to suppliers and integrators of {main}.",
                evolving=evolving,
                main=main,
            ),
        ]
    if ev_type == "die":
        return [
            _make_impact(
                f"Legacy overlap reduction",
                "Economy",
                why=f"Declining activity around {evolving} reduces redundant investment competing with {main}.",
                how=f"Budget and engineering capacity previously split across both areas consolidate toward {main}.",
                evolving=evolving,
                main=main,
            ),
            _make_impact(
                f"Migration path into {main}",
                "Society",
                why=f"Users and teams leaving a fading {evolving} stack need a successor technology.",
                how=f"Organisations reposition {main} as the migration target, transferring workflows and training programs.",
                evolving=evolving,
                main=main,
            ),
        ]
    if ev_type == "merge":
        return [
            _make_impact(
                f"Consolidated stack around {main}",
                "Innovation",
                why=f"Research themes of {evolving} and {main} are converging in the corpus (merge event).",
                how=f"Shared components and unified benchmarks reduce fragmentation and speed integration roadmaps.",
                evolving=evolving,
                main=main,
            ),
            _make_impact(
                "IP & talent concentration",
                "Society",
                why="Overlapping publication topics concentrate expertise in one dominant design.",
                how="Researchers and patents cluster on the merged stack, raising barriers for alternative approaches.",
                evolving=evolving,
                main=main,
            ),
        ]
    if ev_type == "shift":
        ov = ev.get("overlap", "")
        extra = f" ({ov:.0%} keyword overlap)" if isinstance(ov, (int, float)) and ov else ""
        return [
            _make_impact(
                f"Thematic repositioning of {main}",
                "Innovation",
                why=f"Keywords are shifting from {main} toward {evolving}{extra} in the corpus.",
                how=f"{main} roadmaps must adopt {evolving} terminology, methods, and use cases to stay relevant.",
                evolving=evolving,
                main=main,
            ),
        ]
    return [
        _make_impact(
            f"Indirect effect on {main}",
            "Innovation",
            why=f"Temporal change in {evolving} propagates through shared research themes with {main}.",
            how=f"Indirect dependency chains (suppliers, benchmarks, citations) transmit shocks from {evolving} to {main}.",
            evolving=evolving,
            main=main,
        ),
    ]


def _impacts_from_lifecycle(main: str, evolving: str, stage: str, trend: str) -> list[dict]:
    if stage == "introduction":
        return [
            _make_impact(
                f"Early entanglement with {main}",
                "Innovation",
                why=f"{evolving} is at introduction stage ({trend}) while {main} is established—early coupling is likely.",
                how=f"Vendors co-develop prototypes and pilots, embedding {evolving} modules into {main} before standards settle.",
                evolving=evolving,
                main=main,
            ),
        ]
    if stage == "growth":
        return [
            _make_impact(
                f"Co-growth with {main}",
                "Innovation",
                why=f"Both {evolving} and {main} show accelerating publication trends—mutual reinforcement.",
                how=f"Joint benchmarks, datasets, and conference tracks align R&D agendas, lifting both technologies together.",
                evolving=evolving,
                main=main,
            ),
            _make_impact(
                "Supply-chain coupling",
                "Economy",
                why=f"Growth-stage {evolving} builds infrastructure that {main} depends on at scale.",
                how=f"Chips, cloud services, and specialist vendors for {evolving} become prerequisites for advanced {main} products.",
                evolving=evolving,
                main=main,
            ),
        ]
    if stage == "decline":
        return [
            _make_impact(
                "Sunset dependency risk",
                "Governance",
                why=f"{evolving} is in decline—{main} systems may rely on legacy {evolving} integrations.",
                how=f"Teams must migrate off deprecated {evolving} APIs and re-certify {main} products against supported stacks.",
                evolving=evolving,
                main=main,
            ),
        ]
    return [
        _make_impact(
            f"Stable complement to {main}",
            "Innovation",
            why=f"{evolving} is maturing ({trend})—predictable, incremental advances rather than disruption.",
            how=f"{main} vendors integrate mature {evolving} features as stable modules with known performance profiles.",
            evolving=evolving,
            main=main,
        ),
    ]
