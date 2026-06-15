SCENARIO_NARRATIVE_GUIDE = {
    "evolutionary": """NARRATIVE APPROACH (400-600 words):
The following drivers characterise this configuration — let them shape your story:
{anchor_drivers}

Write from the perspective of practitioners living in this future. Show how incremental progress
in these specific technologies changed day-to-day operations in real but undramatic ways.
Avoid grand breakthroughs — the interest is in what actually shipped, what didn't, and what
daily friction looks like under these exact driver states. Ground every technical claim in the
manifestations listed above, not in generic progress language.""",

    "disruptive": """NARRATIVE APPROACH (400-600 words):
These breakthrough drivers are the engine of this configuration — trace their causal chain:
{anchor_drivers}

Show HOW this specific combination of advances created capabilities that were not possible before.
What reinforcing dynamics hold this optimistic configuration together? Who had to change their
practices, infrastructure, or assumptions to realise this? Ground the disruption in the
specific manifestations — avoid generic "AI revolution" language.""",

    "cautionary": """NARRATIVE APPROACH (400-600 words):
These are the drivers that stagnated or failed in this configuration — build your causal chain from them:
{anchor_drivers}

Trace the SPECIFIC failure mode: why did these particular technologies or frameworks not deliver?
What barriers (cost, institutional, technical, political) explain this exact combination of outcomes?
Show how one failure cascades into dependent functions — if measurement degrades, what downstream
function breaks next? Make the failure chain specific to these drivers. Different driver failures
produce different breakdowns — do not default to a generic "regulatory crisis" narrative.""",

    "wildcard": """NARRATIVE APPROACH (400-600 words):
This configuration is polarised — some drivers reached optimistic states while others hit pessimistic extremes:
{anchor_drivers}

The tension between these extremes IS the story. What unexpected event or shift brought this
unstable combination into being? Show the instability: why does this configuration feel
surprising, and what second-order effects does it trigger across the monitoring ecosystem?
Avoid a simple good-vs-bad framing — the interesting question is how these contradictory
conditions coexist and what they force stakeholders to do.""",
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
