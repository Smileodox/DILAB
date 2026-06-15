"""Strategic Framing pipeline step.

Cross-scenario strategy brief: critical uncertainties, no-regret moves,
per-scenario capability gaps / competitive exposure / decision gates,
and a priority recommendation for R&S leadership.

Input:  data/outputs/final_analysis.json
Output: data/outputs/strategic_framing.json
"""
from __future__ import annotations

import json
import os

from src.config import EVAL_MODEL
from src.llm import safe_chat_json
from src.prompts.strategic_framing import STRATEGIC_FRAMING


def _build_scenarios_block(final: dict) -> str:
    rankings_by_id = {
        r["scenario_id"]: r
        for r in final.get("mcda", {}).get("rankings", [])
    }
    assessments_by_id = {a["scenario_id"]: a for a in final["assessments"]}

    scenarios = sorted(
        final["scenarios"],
        key=lambda s: rankings_by_id.get(s["id"], {}).get("rank", 99),
    )

    parts = []
    for i, s in enumerate(scenarios):
        r = rankings_by_id.get(s["id"], {})
        a = assessments_by_id.get(s["id"], {})
        tensions = ", ".join(s.get("key_tensions", []))
        assumptions = "\n".join(
            f"  - {asmp['description']}"
            for asmp in s.get("assumptions", [])
        )
        parts.append(
            f"### Scenario {i} (MCDA Rank #{r.get('rank', '?')}, "
            f"TOPSIS: {r.get('topsis_closeness', 0):.3f})\n"
            f"Title: {s['title']}\n"
            f"Type: {s['type']}\n"
            f"Key tensions: {tensions or 'none listed'}\n"
            f"Driver assumptions:\n{assumptions}\n"
            f"Narrative: {s['narrative'][:500]}\n"
            f"MCDA scores — Impact: {a.get('impact', '?')}/10, "
            f"Probability: {a.get('probability', '?')}/10, "
            f"Actionability: {a.get('actionability', '?')}/10, "
            f"Time horizon: {a.get('time_horizon', '?')}/10, "
            f"Risk severity: {a.get('risk_severity', '?')}/10\n"
            f"Key risks: {a.get('key_risks', 'none listed')}\n"
            f"Early signals (evaluation): {a.get('early_signals', 'none listed')}"
        )
    return "\n\n".join(parts)


def run(
    final_analysis_path: str = "data/outputs/final_analysis.json",
    output_path: str = "data/outputs/strategic_framing.json",
    model: str | None = None,
) -> dict:
    with open(final_analysis_path) as f:
        final = json.load(f)

    n = len(final["scenarios"])
    scenarios_block = _build_scenarios_block(final)

    prompt = STRATEGIC_FRAMING.format(n=n, scenarios_block=scenarios_block)

    result = safe_chat_json(
        prompt,
        system=(
            "You are a senior strategy consultant with deep expertise in defence-grade "
            "telecommunications and spectrum management markets. You are briefing "
            "Rohde & Schwarz leadership on strategic implications of a morphological "
            "foresight analysis. Be concrete, opinionated, and specific — name gaps, "
            "name competitors, name decision timelines."
        ),
        model=model or EVAL_MODEL,
    )

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    n_uncert = len(result.get("critical_uncertainties", []))
    n_moves = len(result.get("no_regret_moves", []))
    n_strat = len(result.get("scenario_strategy", []))
    priority = result.get("recommended_priority", {}).get("scenario_title", "none")
    print(f"  {n_uncert} critical uncertainties, {n_moves} no-regret moves, "
          f"{n_strat} scenario strategies")
    print(f"  Priority scenario: {priority}")

    return result
