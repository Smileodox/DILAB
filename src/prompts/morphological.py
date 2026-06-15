MANIFESTATION_DETERMINE = """Determine 2-4 possible future manifestations for this technology driver
in the regulatory frequency monitoring domain, looking ahead to 2035.

TECHNOLOGY DRIVER: {driver_name}
DESCRIPTION: {driver_description}
ORIGIN: {driver_origin} (confidence: {driver_confidence})

SOURCE MATERIAL:
{rag_chunks}

A "manifestation" is a specific, domain-grounded state this technology could reach by 2035.
Do NOT use generic labels like "breakthrough" or "stagnation". Instead, describe WHAT
specifically happens in this technology area.

RULES:
- Each manifestation must be SPECIFIC to this technology (not generic progress labels)
- Manifestations must be MUTUALLY EXCLUSIVE (a driver can only be in one state)
- Manifestations must be COLLECTIVELY EXHAUSTIVE (cover the realistic range of outcomes)
- Include at least one optimistic and one pessimistic manifestation
- Each manifestation needs a concrete description grounded in the source material
- Order from most optimistic to most pessimistic

EXAMPLE (for a hypothetical "Wideband RF Frontend" driver):
  1. "Sub-THz coverage achieved" — single platform covers 8 kHz to 300 GHz
  2. "Millimeter-wave extension" — coverage extends to 110 GHz, sub-THz via external module
  3. "Current range maintained" — 8 kHz to 40 GHz with incremental sensitivity gains only

Return JSON:
{{
  "manifestations": [
    {{
      "label": "short specific label (max 10 words)",
      "description": "2-3 sentences describing what this state means concretely for spectrum monitoring",
      "plausibility": "high" or "medium" or "low",
      "grounding": "which source evidence supports this possibility"
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


SCENARIO_GENERATE_MORPHOLOGICAL = """Generate a 2035 scenario for the regulatory frequency monitoring domain
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
Time horizon: 2035

Return JSON:
{{
  "title": "short descriptive title — name the specific dynamic, not the generic outcome type",
  "narrative": "the scenario narrative (400-600 words)",
  "perspective": "3-5 word framing phrase capturing the core narrative angle",
  "key_changes": ["3-5 most important changes from today"],
  "key_tensions": ["1-3 unresolved tensions"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""
