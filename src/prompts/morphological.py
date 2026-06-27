MANIFESTATION_DETERMINE = """Determine 2-4 possible future manifestations for this technology driver
in the {domain} domain, looking ahead to {horizon}.

TECHNOLOGY DRIVER: {driver_name}
DESCRIPTION: {driver_description}
ORIGIN: {driver_origin} (confidence: {driver_confidence})

SOURCE MATERIAL:
{rag_chunks}

A "manifestation" is a specific, domain-grounded state this technology could reach by {horizon}.
Do NOT use generic labels like "breakthrough" or "stagnation". Instead, describe WHAT
specifically happens in this technology area.

RULES:
- Each manifestation must be SPECIFIC to this technology (not generic progress labels)
- Manifestations must be MUTUALLY EXCLUSIVE (a driver can only be in one state)
- Manifestations must be COLLECTIVELY EXHAUSTIVE (cover the realistic range of outcomes)
- Include at least one optimistic and one pessimistic manifestation
- Each manifestation needs a concrete description grounded in the source material
- Order from most optimistic to most pessimistic

EXAMPLE of specific, distinct manifestations (not generic progress labels):
{manifestation_example}

Return JSON:
{{
  "manifestations": [
    {{
      "label": "short specific label (max 10 words)",
      "description": "2-3 sentences describing what this state means concretely for {domain}",
      "plausibility": "high" or "medium" or "low",
      "grounding": "which source evidence supports this possibility"
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


SCENARIO_GENERATE_MORPHOLOGICAL = """Generate a {horizon} scenario for the {domain} domain
from this CIB-consistent driver configuration:

DRIVER MANIFESTATIONS — these define the scenario, let them lead the narrative:
{driver_manifestations_block}

KEY CROSS-IMPACT DYNAMICS:
{cib_context}

SOURCE MATERIAL:
{rag_chunks}

GROUNDING RULE: Base all technical claims on the source material and driver manifestations above.
Mark unsupported claims with [Extrapolation].

{narrative_guide}

{existing_titles_block}

Your scenario MUST be internally consistent with ALL driver manifestations above.
Show WHY this specific combination of states holds together — what reinforcing dynamics
make it stable, and what would have to change for it to unravel.

Scenario type (for classification only): {scenario_type}
Time horizon: {horizon}

Return JSON:
{{
  "title": "short descriptive title — name the specific dynamic, not the generic outcome type",
  "narrative": "the scenario narrative (400-600 words)",
  "perspective": "3-5 word framing phrase capturing the core narrative angle",
  "key_changes": ["3-5 most important changes from today"],
  "key_tensions": ["1-3 unresolved tensions"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


SCENARIO_GENERATE_MORPHOLOGICAL_SHORT = """Generate a concise {horizon} scenario for the {domain} domain
from this driver configuration.

DRIVER MANIFESTATIONS — these define the scenario, let them lead:
{driver_manifestations_block}

KEY CROSS-IMPACT DYNAMICS (context only):
{cib_context}

SOURCE MATERIAL:
{rag_chunks}

GROUNDING RULE: Base all technical claims on the source material and the driver
manifestations above. Mark any unsupported claim with [Extrapolation]. Prefer fewer,
well-grounded statements over broad speculation.

{narrative_guide}

{existing_titles_block}

Keep the narrative internally consistent with the driver manifestations. Describe the
state of the world under this configuration — do NOT spin out long causal chains,
second-order effects, or how the configuration might eventually unravel.

Time horizon: {horizon}

Return JSON:
{{
  "title": "short descriptive title — name the specific dynamic, not a generic outcome",
  "narrative": "the scenario narrative ({word_count} words)",
  "perspective": "3-5 word framing phrase capturing the core narrative angle",
  "key_tensions": ["1-2 unresolved tensions — omit if none are natural"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


SCENARIO_GENERATE_MORPHOLOGICAL_NEUTRAL = """Generate a {horizon} scenario for the {domain} domain that is consistent
with the following driver configuration.

DRIVER MANIFESTATIONS — these define the scenario:
{driver_manifestations_block}

CROSS-IMPACT CONTEXT:
{cib_context}

SOURCE MATERIAL:
{rag_chunks}

Write a coherent account of how {domain} looks in {horizon} under this
specific combination of driver states. Stay consistent with the manifestations above and
ground technical claims in the source material where possible. Beyond that, write the
scenario however you judge best — there is no prescribed length, structure, tone, or framing.

{existing_titles_block}

Return JSON:
{{
  "title": "a short, specific title for this scenario",
  "narrative": "the scenario narrative",
  "perspective": "a 3-5 word framing phrase",
  "key_tensions": ["unresolved tensions, if any are natural — otherwise omit"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""
