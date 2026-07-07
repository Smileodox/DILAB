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
