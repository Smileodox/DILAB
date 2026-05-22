SCENARIO_ASSESS = """You are evaluating {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).
Compare them against each other and score each one on FIVE criteria.

{scenarios_block}

Based ONLY on the following source material, evaluate ALL scenarios comparatively.

SOURCE MATERIAL:
{rag_chunks}

SCORING CALIBRATION — use the full 1-10 range for ALL criteria:

IMPACT: How transformative is this scenario for R&S products and the domain?
  1-3: incremental improvements, minor operational changes
  4-5: notable changes requiring product adaptation
  6-7: significant transformation of workflows or capabilities
  8-9: major paradigm shift in the domain
  10: complete disruption, current approaches become obsolete

PROBABILITY: How likely is this scenario to materialize by 2035?
  1-3: speculative/unlikely
  4-5: possible
  6-7: plausible
  8-9: likely
  10: near certain

ACTIONABILITY: How much can R&S proactively prepare for or influence this scenario?
  1-3: little R&S can do; driven by external forces (geopolitics, regulation)
  4-5: some preparation possible but limited leverage
  6-7: clear R&D or strategic actions available
  8-9: strong preparation path with concrete product/technology moves
  10: R&S can directly shape the outcome through immediate action

TIME HORIZON (10 = imminent): How soon will this scenario's effects be felt?
  1-3: beyond 2035, very long-term
  4-5: mid-term (2030-2035)
  6-7: emerging now, materializing by 2028-2030
  8-9: already underway, significant by 2026-2027
  10: immediate, happening now

RISK SEVERITY: How severe are the risks if R&S fails to prepare?
  1-3: minor competitive disadvantage
  4-5: notable market share loss or missed opportunity
  6-7: significant strategic threat
  8-9: existential risk to product lines
  10: complete market disruption, business viability threatened

CRITICAL RULES:
- Scenarios MUST receive DIFFERENT impact scores (no ties allowed)
- Scenarios MUST receive DIFFERENT probability scores (no ties allowed)
- For actionability, time_horizon, and risk_severity: avoid ties where possible
- Evolutionary scenarios: generally HIGHER probability, potentially LOWER impact
- Disruptive scenarios: generally LOWER probability, potentially HIGHER impact
- Cautionary scenarios: assess the probability of the FAILURE MODE occurring
- Wildcard scenarios: probability should reflect low-likelihood nature; impact should reflect cascading effects

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "impact": (float 1-10),
      "probability": (float 1-10),
      "actionability": (float 1-10),
      "time_horizon": (float 1-10),
      "risk_severity": (float 1-10),
      "reasoning": "justification referencing source material and comparison to other scenarios",
      "key_risks": "what risks does this scenario pose for R&S",
      "early_signals": "what observable signals today would indicate this scenario is unfolding",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""
