SCENARIO_ASSESS = """You are evaluating {n} future scenarios for {actor} (role: {actor_role}).
Compare them against each other and score each one on FIVE criteria.

{scenarios_block}

Based ONLY on the following source material, evaluate ALL scenarios comparatively.

SOURCE MATERIAL:
{rag_chunks}

SCORING CALIBRATION — use the full 1-10 range for ALL criteria:

IMPACT: How transformative is this scenario for {actor} and the {domain} domain?
  1-3: incremental improvements, minor operational changes
  4-5: notable changes requiring product adaptation
  6-7: significant transformation of workflows or capabilities
  8-9: major paradigm shift in the domain
  10: complete disruption, current approaches become obsolete

PROBABILITY: How likely is this scenario to materialize by {horizon}?
  1-3: speculative/unlikely
  4-5: possible
  6-7: plausible
  8-9: likely
  10: near certain

ACTIONABILITY: How much can {actor} proactively prepare for or influence this scenario?
  1-3: little {actor} can do; driven by external forces (geopolitics, regulation)
  4-5: some preparation possible but limited leverage
  6-7: clear R&D or strategic actions available
  8-9: strong preparation path with concrete product/technology moves
  10: {actor} can directly shape the outcome through immediate action

TIME HORIZON (10 = imminent): How soon will this scenario's effects be felt?
  1-3: beyond {horizon}, very long-term
  4-5: mid-term (around {horizon})
  6-7: emerging now, materializing well before {horizon}
  8-9: already underway, significant within the next few years
  10: immediate, happening now

RISK SEVERITY: How severe are the risks if {actor} fails to prepare?
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
      "key_risks": "what risks does this scenario pose for {actor}",
      "early_signals": "what observable signals today would indicate this scenario is unfolding",
      "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
    }}
  ]
}}"""


# --- Pointwise, evidence-grounded auditor (primary evaluation mode) -------------------
# One scenario per call: no position bias, a bounded per-scenario evidence set, and fact
# extraction BEFORE scoring to counter LLM positivity bias. Emits impact + probability AND
# the three remaining MCDA criteria (actionability, time_horizon, risk_severity) as numeric
# scores so the grounded assessment feeds AHP+TOPSIS directly, plus grounding/audit fields.

SCENARIO_POINTWISE_EVIDENCE_ASSESS = """You are an expert technology forecasting auditor.
Evaluate ONE future scenario against its own labeled evidence set.

DOMAIN CONTEXT:
- Domain: {domain} ({domain_description})
- Target horizon: {horizon}
- Organization context: {actor} — {actor_role}

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
- Probability asks: how plausible is this future by {horizon} given the evidence?
- Do not let high impact inflate probability.
- Do not let low probability reduce hypothetical impact.
- Do not reward narrative excitement or writing quality.

RUBRICS - ABSTRACT TIERS (use the full 1-10 range for every score):
Impact — how transformative for {actor} and the {domain} domain:
- 1-3: incremental improvements, minor operational changes
- 4-5: notable changes requiring product adaptation
- 6-7: significant transformation of workflows or capabilities
- 8-9: major paradigm shift in the domain
- 10: complete disruption, current approaches become obsolete

Probability by {horizon}:
- 1-3: speculative/unlikely
- 4-5: possible but uncertain
- 6-7: plausible
- 8-9: likely
- 10: near certain

Actionability — how much {actor} can proactively prepare for or influence this scenario:
- 1-3: little {actor} can do; driven by external forces (geopolitics, regulation)
- 4-5: some preparation possible but limited leverage
- 6-7: clear R&D or strategic actions available
- 8-9: strong preparation path with concrete product/technology moves
- 10: {actor} can directly shape the outcome through immediate action

Time horizon (10 = imminent) — how soon this scenario's effects are felt:
- 1-3: beyond {horizon}, very long-term
- 4-5: mid-term (around {horizon})
- 6-7: emerging now, materializing well before {horizon}
- 8-9: already underway, significant within the next few years
- 10: immediate, happening now

Risk severity — how severe the risks if {actor} fails to prepare:
- 1-3: minor competitive disadvantage
- 4-5: notable market share loss or missed opportunity
- 6-7: significant strategic threat
- 8-9: existential risk to product lines
- 10: complete market disruption, business viability threatened

Grounding strength:
- strong: assessment is mostly directly supported by retrieved evidence
- moderate: assessment requires reasonable inference from retrieved evidence, with no external facts introduced
- weak: assessment depends on assumptions insufficiently supported by retrieved evidence

Think in this exact order:
1. Extract supporting and limiting evidence.
2. Identify inferences and unsupported claims.
3. Assess risks and score their severity.
4. Assess early signals, actionability, and time horizon, and score them.
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
    "analysis": "risks for {actor} if this scenario unfolds",
    "severity_justification": "why these risks are strategically important or limited",
    "severity_score": (integer 1-10)
  }},
  "signals_and_actionability": {{
    "observable_signals": "2-3 observable signals that would indicate this scenario is unfolding",
    "recommended_actions": "2-3 concrete actions {actor} could take now",
    "actionability_score": (integer 1-10),
    "time_horizon_score": (integer 1-10)
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
    "maturity_and_barrier_analysis": "technical maturity, adoption barriers, and timeline plausibility by {horizon}",
    "score_boundary_justification": "why the score fits its tier and why not the tier above or below",
    "final_probability_score": (integer 1-10)
  }},
  "source_evidence_labels_used": ["E1", "E2"]
}}"""


SCENARIO_POINTWISE_SYSTEM = (
    "You are a careful technology forecasting auditor. Use only provided evidence "
    "and reasonable inference from that evidence; do not introduce external facts."
)
