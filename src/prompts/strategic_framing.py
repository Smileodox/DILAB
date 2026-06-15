STRATEGIC_FRAMING = """You are a strategy consultant briefing the Rohde & Schwarz leadership team on their spectrum monitoring portfolio. A morphological foresight analysis has produced {n} internally-consistent scenarios for the 2035 horizon, ranked by multi-criteria analysis (AHP+TOPSIS).

MCDA-RANKED SCENARIOS:
{scenarios_block}

Your task: translate these foresight outputs into actionable strategy intelligence. Be concrete and specific to R&S's spectrum monitoring portfolio — not generic technology advice.

STEP 1 — CRITICAL UNCERTAINTIES (2-3 axes max):
Identify the uncertainties that most DIFFERENTIATE these scenarios from each other. These are not important trends — they are the specific decision forks where R&S's position changes fundamentally. For each axis: what resolves it high vs. low, and which scenarios fall on each side.

STEP 2 — NO-REGRET MOVES (3-5 actions):
Strategic actions that create value regardless of which scenario materialises. These must be concrete — specific capability investments, product architecture decisions, or partnership moves. For each: which scenarios it hedges and why it is valuable even if those scenarios never arrive.

STEP 3 — PER-SCENARIO STRATEGY:
For EACH scenario (use the scenario_index from the input):
- capability_gaps: What specific technical or organisational capabilities would R&S lack if this materialised tomorrow? Name the gap, not the general category.
- competitive_exposure: How would Teledyne, Keysight, Rohde (different entity), and emerging vendors likely respond? Who benefits, who loses market share?
- decision_gate: The ONE decision R&S must make to preserve optionality. Format: "By [year], R&S must decide whether to [specific action] — delaying past this point forecloses [outcome]."
- early_indicators: 2-3 specific, monitorable signals (ITU working party outputs, customer procurement shifts, standards body votes, technology demonstrations) that would confirm this scenario is forming.

STEP 4 — PRIORITY RECOMMENDATION:
Given MCDA rankings and strategic exposure: which scenario should R&S treat as primary planning scenario, and what are exactly 3 actions to take in the next 12 months?

Return JSON:
{{
  "critical_uncertainties": [
    {{
      "axis": "concise name for the uncertainty axis",
      "description": "the specific fork and what changes at each extreme for R&S",
      "scenarios_high": ["titles where this resolves favourably for R&S"],
      "scenarios_low": ["titles where this resolves unfavourably for R&S"]
    }}
  ],
  "no_regret_moves": [
    {{
      "action": "concrete strategic action",
      "rationale": "why this hedges across scenarios and has standalone value",
      "scenarios_covered": ["scenario titles this is most critical for"],
      "horizon": "immediate|short_term|medium_term"
    }}
  ],
  "scenario_strategy": [
    {{
      "scenario_index": 0,
      "scenario_title": "title from input",
      "mcda_rank": 1,
      "capability_gaps": "specific named gaps in R&S current portfolio",
      "competitive_exposure": "how named competitors respond; who wins/loses",
      "decision_gate": "By [year], R&S must decide whether to [action] — delaying forecloses [outcome]",
      "early_indicators": ["specific monitorable signal 1", "signal 2"]
    }}
  ],
  "recommended_priority": {{
    "scenario_title": "title of primary planning scenario",
    "rationale": "why this scenario warrants primary planning focus over the others",
    "immediate_actions": ["action 1 within 12 months", "action 2", "action 3"]
  }}
}}"""
