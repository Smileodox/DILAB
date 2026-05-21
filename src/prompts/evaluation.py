SCENARIO_ASSESS = """You are evaluating {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).
Compare them against each other and score each one.

{scenarios_block}

Based ONLY on the following source material, evaluate ALL scenarios comparatively.

SOURCE MATERIAL:
{rag_chunks}

SCORING CALIBRATION — use the full range:
- Impact 1-3: incremental improvements, minor operational changes
- Impact 4-5: notable changes requiring product adaptation
- Impact 6-7: significant transformation of workflows or capabilities
- Impact 8-9: major paradigm shift in the domain
- Impact 10: complete disruption, current approaches become obsolete
- Probability follows similar logic: 1-3 = speculative/unlikely, 4-5 = possible, 6-7 = plausible, 8-9 = likely, 10 = near certain

CRITICAL RULES:
- Scenarios MUST receive DIFFERENT impact scores (no ties allowed)
- Scenarios MUST receive DIFFERENT probability scores (no ties allowed)
- Evolutionary scenarios: generally HIGHER probability, potentially LOWER impact
- Disruptive scenarios: generally LOWER probability, potentially HIGHER impact
- Cautionary scenarios: assess the probability of the FAILURE MODE occurring, not just tech progress
- Wildcard scenarios: probability should reflect the low-likelihood nature; impact should reflect cascading effects

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "impact": (float 1-10),
      "probability": (float 1-10),
      "reasoning": "justification referencing source material and comparison to other scenarios",
      "key_risks": "what risks does this scenario pose for R&S",
      "early_signals": "what observable signals today would indicate this scenario is unfolding",
      "actionability": "what should R&S do now to prepare",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""
