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

POSITION BIAS MITIGATION — read before scoring:
LLM judges systematically favor scenarios based on list position rather than merit. You MUST counteract this:
- Scenario numbers (0, 1, 2, ...) are arbitrary identifiers ONLY — they are NOT rankings, priority, or quality order
- A scenario appearing first is NOT more probable or impactful; one appearing last is NOT less so
- Score each scenario solely on its content, assumptions, and fit with the source material relative to the OTHER scenarios
- Before finalizing scores, mentally shuffle the list order and verify your scores would stay the same

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

SCENARIO_ASSESS_SYSTEM = (
    "You are a strategic technology analyst at Rohde & Schwarz evaluating future scenarios "
    "for spectrum monitoring. Ignore presentation order — score only on scenario merit."
)

SCENARIO_IMPACT_ASSESS = """You are evaluating ONLY the IMPACT of {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).

Do NOT evaluate probability, risks, early signals, or actionability in this pass.
Your only task is to compare the scenarios and score how much each scenario would change the regulatory frequency monitoring domain if it occurred.

{scenarios_block}

Based ONLY on the following source material, evaluate impact comparatively.

SOURCE MATERIAL:
{rag_chunks}

IMPACT CALIBRATION - use the full range:
- 1-3: incremental improvements, minor operational changes
- 4-5: notable changes requiring product adaptation
- 6-7: significant transformation of workflows or capabilities
- 8-9: major paradigm shift in the domain
- 10: complete disruption, current approaches become obsolete

POSITION BIAS MITIGATION:
- Scenario numbers are arbitrary identifiers ONLY - they are NOT rankings
- Ignore first/last placement when scoring
- Before finalizing scores, mentally shuffle the list order and verify your impact scores would stay the same

CRITICAL RULES:
- Score ONLY impact
- Ignore how likely the scenario is
- Scenarios MUST receive DIFFERENT impact scores (no ties allowed)
- Base the score on domain change, product implications, workflow transformation, and disruption potential

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "impact": (float 1-10),
      "impact_reasoning": "brief justification referencing source material and comparison to other scenarios",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""


SCENARIO_PROBABILITY_ASSESS = """You are evaluating ONLY the PROBABILITY of {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).

Do NOT evaluate impact, risks, early signals, or actionability in this pass.
Your only task is to compare the scenarios and score how likely each scenario is by 2035.

{scenarios_block}

Based ONLY on the following source material, evaluate probability comparatively.

SOURCE MATERIAL:
{rag_chunks}

PROBABILITY CALIBRATION - use the full range:
- 1-3: speculative/unlikely
- 4-5: possible but uncertain
- 6-7: plausible
- 8-9: likely
- 10: near certain

POSITION BIAS MITIGATION:
- Scenario numbers are arbitrary identifiers ONLY - they are NOT rankings
- Ignore first/last placement when scoring
- Before finalizing scores, mentally shuffle the list order and verify your probability scores would stay the same

CRITICAL RULES:
- Score ONLY probability
- Ignore how disruptive or exciting the scenario is
- Scenarios MUST receive DIFFERENT probability scores (no ties allowed)
- Evolutionary scenarios are often more probable, but still judge the concrete assumptions
- Disruptive scenarios are often less probable, but do not penalize them automatically if the source material supports them
- Cautionary scenarios: assess probability of the failure mode occurring
- Wildcard scenarios: probability should reflect low-likelihood, high-uncertainty developments

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "probability": (float 1-10),
      "probability_reasoning": "brief justification referencing source material and comparison to other scenarios",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""


SCENARIO_RISK_ASSESS = """You are evaluating ONLY RISKS for {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).

Do NOT score impact or probability in this pass.
Your only task is to identify the most important strategic, technical, market, regulatory, or operational risks each scenario creates for R&S.

{scenarios_block}

Based ONLY on the following source material, identify risks comparatively.

SOURCE MATERIAL:
{rag_chunks}

POSITION BIAS MITIGATION:
- Scenario numbers are arbitrary identifiers ONLY - they are NOT rankings
- Ignore first/last placement when identifying risks
- Before finalizing, mentally shuffle the list order and verify your risk assessment would stay the same

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "key_risks": "concise risk assessment for R&S",
      "risk_reasoning": "brief justification referencing source material",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""


SCENARIO_SIGNALS_ASSESS = """You are evaluating ONLY EARLY SIGNALS and ACTIONABILITY for {n} future scenarios for a spectrum monitoring equipment manufacturer (Rohde & Schwarz).

Do NOT score impact or probability in this pass.
Your task is to identify observable early signals that indicate the scenario is unfolding and actions R&S could take now.

{scenarios_block}

Based ONLY on the following source material, identify early signals and actionability comparatively.

SOURCE MATERIAL:
{rag_chunks}

POSITION BIAS MITIGATION:
- Scenario numbers are arbitrary identifiers ONLY - they are NOT rankings
- Ignore first/last placement when identifying signals and actions
- Before finalizing, mentally shuffle the list order and verify your assessment would stay the same

Return JSON:
{{
  "assessments": [
    {{
      "scenario_index": 0,
      "early_signals": "observable signals today or in the near future",
      "actionability": "what R&S should do now to prepare",
      "signals_reasoning": "brief justification referencing source material",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""


SCENARIO_POINTWISE_EVIDENCE_ASSESS = """You are an expert technology forecasting auditor.
Evaluate ONE technology scenario against its own labeled evidence set.

DOMAIN CONTEXT:
- Domain: {domain_name}
- Target horizon: {target_year}
- Organization context: {org_context}

SCENARIO:
Title: {scenario_title}
Type: {scenario_type}
Perspective: {scenario_perspective}

Assumptions:
{scenario_assumptions}

Narrative:
{scenario_narrative}

LABELED EVIDENCE:
{evidence_block}

CIB CONTEXT:
{cib_context}

GROUNDING CONSTRAINT - CRITICAL:
- Use the retrieved evidence as the primary basis for your assessment.
- You may draw reasonable conclusions that logically follow from the provided evidence.
- Do NOT introduce external facts, technologies, market developments, organizations, dates, or assumptions that are not supported by the retrieved source material.
- If a scenario claim is directly supported, cite evidence labels like [E1].
- If a scenario claim requires inference, label it as "inference_from_evidence" and explain which evidence it follows from.
- If a scenario claim is not supported by evidence or reasonable inference from evidence, list it under unsupported_claims.

DIMENSION ISOLATION CONSTRAINT - CRITICAL:
- Impact asks: if this future occurs, how significant are the consequences?
- Probability asks: how plausible is this future by {target_year} given the evidence?
- Do not let high impact inflate probability.
- Do not let low probability reduce hypothetical impact.
- Do not reward narrative excitement or writing quality.

RUBRICS - ABSTRACT TIERS:
Impact:
- 1-3: incremental improvements, minor operational changes
- 4-5: notable changes requiring product adaptation
- 6-7: significant transformation of workflows or capabilities
- 8-9: major paradigm shift in the domain
- 10: complete disruption, current approaches become obsolete

Probability by {target_year}:
- 1-3: speculative/unlikely
- 4-5: possible but uncertain
- 6-7: plausible
- 8-9: likely
- 10: near certain

Grounding strength:
- strong: assessment is mostly directly supported by retrieved evidence
- moderate: assessment requires reasonable inference from retrieved evidence, with no external facts introduced
- weak: assessment depends on assumptions insufficiently supported by retrieved evidence

Think in this exact order:
1. Extract supporting and limiting evidence.
2. Identify inferences and unsupported claims.
3. Assess risks.
4. Assess early signals and actionability.
5. Check CIB consistency.
6. Score impact with boundary justification.
7. Score probability with boundary justification.

Return valid JSON:
{{
  "rag_fact_extraction": {{
    "supporting_evidence": ["2-4 evidence-backed facts, each citing labels like [E1]"],
    "contradictory_or_limiting_evidence": ["facts that limit or complicate the scenario, each citing labels like [E2]"],
    "inference_from_evidence": ["reasonable inferences and the evidence labels they follow from, or 'None'"],
    "unsupported_claims": ["specific scenario claims not backed by evidence or reasonable inference, or 'None'"]
  }},
  "grounding_strength": "strong | moderate | weak",
  "grounding_reason": "why this grounding label applies",
  "risks": {{
    "analysis": "risks for the organization if this scenario unfolds",
    "severity_justification": "why these risks are strategically important or limited"
  }},
  "signals_and_actionability": {{
    "observable_signals": "2-3 observable signals that would indicate this scenario is unfolding",
    "recommended_actions": "2-3 concrete actions the organization could take now"
  }},
  "cib_consistency": {{
    "strength": "strong | moderate | weak | not_applicable",
    "reflected_dynamics": ["important CIB promoting/inhibiting relationships that the scenario reflects, or 'None'"],
    "unexplained_tensions": ["important CIB tensions not explained by the scenario, or 'None'"],
    "reason": "brief explanation of the CIB consistency assessment"
  }},
  "impact_evaluation": {{
    "workflow_delta_description": "how workflows/products/capabilities would change if this scenario occurs",
    "score_boundary_justification": "why the score fits its tier and why not the tier above or below",
    "final_impact_score": (integer 1-10)
  }},
  "probability_evaluation": {{
    "maturity_and_barrier_analysis": "technical maturity, adoption barriers, and timeline plausibility by {target_year}",
    "score_boundary_justification": "why the score fits its tier and why not the tier above or below",
    "final_probability_score": (integer 1-10)
  }},
  "source_evidence_labels_used": ["E1", "E2"]
}}"""


SCENARIO_POINTWISE_SYSTEM = (
    "You are a careful technology forecasting auditor. Use only provided evidence "
    "and reasonable inference from that evidence; do not introduce external facts."
)
