BOM_DECOMPOSE = """You are analyzing a component from a regulatory frequency monitoring system.

Parent context: {parent_context}
Component to decompose: {component_name}
Component description: {component_description}

Based ONLY on the following source material, identify the sub-components or sub-technologies of this component.

SOURCE MATERIAL:
{rag_chunks}

Return JSON with this structure:
{{
  "components": [
    {{
      "name": "component name",
      "description": "brief technical description",
      "is_leaf": true/false (true if this is a fundamental technology or material)
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}

Only include components you can support with the provided source material. If the source material doesn't contain enough information, return fewer components rather than guessing."""


BOM_CLASSIFY_DRIVER = """Given this technology component from a regulatory frequency monitoring product BOM:

Name: {name}
Description: {description}
BOM Path: {bom_path}

Is this a Technology Driver — meaning a technology with active R&D, expected performance improvements, or potential for disruption in the next 5-15 years?

Return JSON:
{{
  "is_tech_driver": true/false,
  "reasoning": "why or why not"
}}"""


TREND_SCAN = """You are scanning for technology trends relevant to regulatory frequency monitoring and spectrum management.

Based ONLY on the following source material, identify major technology trends that could impact this domain in the next 5-15 years.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "trends": [
    {{
      "name": "trend name",
      "description": "what is this trend",
      "relevance": "how does this impact regulatory frequency monitoring specifically",
      "timeframe": "near-term (0-5y) / mid-term (5-10y) / long-term (10-15y)"
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}

Only include trends supported by the source material."""


TREND_IMPACT = """Evaluate the impact of this technology trend on regulatory frequency monitoring:

Trend: {trend_name}
Description: {trend_description}

Based ONLY on the following source material, assess the impact.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "impact_level": "high/medium/low/none",
  "impact_description": "specific ways this trend changes regulatory frequency monitoring",
  "affected_areas": ["list of product areas affected"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


MERGE_DRIVERS = """You have two lists of technology drivers identified through different methods for the regulatory frequency monitoring domain.

BOTTOM-UP DRIVERS (from product BOM decomposition):
{bom_drivers}

TOP-DOWN DRIVERS (from technology trend scanning):
{trend_drivers}

Map these lists onto each other:
1. Find matches: a BOM driver and a trend driver that describe the same or closely related technology
2. Identify BOM-only drivers: present in products but not flagged as trends
3. Identify trend-only drivers: emerging trends not yet in current products

Return JSON:
{{
  "matches": [
    {{
      "bom_driver_id": "id",
      "trend_driver_id": "id",
      "unified_name": "best name for this driver",
      "reasoning": "why these are the same technology"
    }}
  ],
  "bom_only": ["list of bom driver ids with no trend match"],
  "trend_only": ["list of trend driver ids with no bom match"]
}}"""


CIB_EVALUATE = """Evaluate the cross-impact between two technology drivers in the regulatory frequency monitoring domain.

Driver A: {driver_a_name} — {driver_a_description}
Driver B: {driver_b_name} — {driver_b_description}

Question: If Driver A makes significant progress (breakthrough), how does that affect the development of Driver B?

STEP 1 — INHIBITION ANALYSIS (do this first):
List all ways that progress in A could HARM, SLOW, or REDUCE the need for B:
- Does A compete with B for R&D budget or engineering talent?
- Does A make B partially or fully obsolete?
- Does A's standards/approach lock out B's approach?
- Does A capture regulatory attention away from B?
- Does A reduce market demand for B?

STEP 2 — SCORE BOTH DIMENSIONS:

PROMOTING (0-3): How much does progress in A help B?
- 0 = no benefit to B
- 1 = minor synergy
- 2 = significant enablement
- 3 = A is a critical prerequisite for B

INHIBITING (0-3): How much does progress in A hinder B?
- 0 = genuinely no harm — A and B are in completely separate domains with no shared resources
- 1 = minor resource competition or slight obsolescence pressure
- 2 = significant funding/talent diversion or partial obsolescence
- 3 = A directly replaces or blocks B

SCORING CALIBRATION:
The scale is symmetric and should be fully utilized. A score of 0 on both dimensions means the technologies are genuinely independent. Most technology pairs in a shared domain will have at least minor interactions.

After scoring, mentally verify: "Would an expert in this domain agree that these two technologies interact at this intensity level?" Adjust if your scores cluster too narrowly — the full 0-3 range exists because real technology interactions vary widely in strength.

Many technology pairs have BOTH promoting AND inhibiting effects. Score each dimension independently and honestly.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "inhibition_analysis": "list the specific ways A could harm B (from Step 1)",
  "promoting_score": (integer 0-3),
  "promoting_reasoning": "specific mechanism",
  "inhibiting_score": (integer 0-3),
  "inhibiting_reasoning": "specific mechanism",
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


SCENARIO_NARRATIVE_GUIDE = {
    "evolutionary": """Write a pragmatic, grounded narrative (400-600 words) structured as:
1. SETTING: A typical workday for a spectrum monitoring operator in 2035
2. CAPABILITIES: Which technologies improved incrementally and how they changed daily operations
3. PRACTICAL CONSTRAINTS: Budget realities, procurement delays, training gaps, or legacy systems still in use
4. OUTLOOK: What remains unchanged or underperforms despite steady progress""",

    "disruptive": """Write an ambitious but honest narrative (400-600 words) structured as:
1. SETTING: The moment a breakthrough technology changes the game for spectrum monitoring
2. NEW POSSIBILITIES: What becomes possible that was not before — specific operational capabilities
3. TRANSITION COSTS: Retraining, legacy displacement, integration challenges, institutional resistance
4. WINNERS AND LOSERS: Who benefits and who is left behind in this transformation""",

    "cautionary": """Write a critical, clear-eyed narrative (400-600 words) structured as:
1. SETTING: A regulatory crisis, procurement failure, or operational breakdown in 2035
2. THE PROMISE: What technologies were expected to deliver by 2035
3. THE FAILURE: The deployment barrier, cost explosion, skills shortage, or institutional failure that prevented delivery
4. CONSEQUENCES: Cascading effects of the gap between expectation and reality — for regulators, manufacturers, and citizens""",

    "wildcard": """Write a surprising narrative (400-600 words) structured as:
1. THE TRIGGER: The geopolitical event, scientific discovery, or regulatory shift that nobody planned for
2. THE CASCADE: Second-order effects rippling through spectrum monitoring infrastructure and operations
3. ADAPTATION: Who pivots successfully and who is caught unprepared
4. THE NEW NORMAL: How the domain reshapes itself after the disruption""",
}

SCENARIO_GENERATE = """Generate a future scenario for the regulatory frequency monitoring domain based on these technology driver assumptions:

{driver_assumptions}

Scenario type: {scenario_type}
Scenario perspective: {perspective}
Time horizon: 2035
{existing_titles_block}

CIB CONTEXT (key cross-impacts shaping this scenario):
{cib_context}

SOURCE MATERIAL:
{rag_chunks}

GROUNDING RULE: Base all technical claims on the provided source material. If you make a claim not directly supported by the sources, prefix it with "[Extrapolation]" so readers can distinguish sourced facts from inference.

{narrative_guide}

Frame the narrative around the perspective "{perspective}".
The scenario MUST be internally consistent with all stated driver assumptions.
Show how the cross-impact dynamics from the CIB data play out concretely.

Return JSON:
{{
  "title": "short descriptive title (must be clearly distinct from any previously generated titles)",
  "narrative": "the scenario narrative",
  "key_changes": ["list of 3-5 most important changes from today"],
  "key_tensions": ["list of 1-3 unresolved tensions or tradeoffs — omit if none are natural for this scenario type"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


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
