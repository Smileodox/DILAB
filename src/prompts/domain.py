"""Prompts for the domain abstraction step — infer the domain framing from a KB.

These are the only prompts allowed to be domain-neutral by construction: they READ the
docked knowledge base and OUTPUT the domain specifics (label, system, horizon, actor,
calibration examples, retrieval queries, expert personas) that every other prompt then
consumes via DomainProfile.prompt_kwargs(). Dock a different KB → different profile.
"""

DOMAIN_PROFILE_EXTRACT = """You are configuring a domain-agnostic strategic technology foresight pipeline for a NEW
knowledge base. Read the sample below and infer the DOMAIN this corpus is about, so the
pipeline can analyse it WITHOUT any hardwired assumptions.

KNOWLEDGE BASE SAMPLE:
{kb_sample}

Infer the following grounded ONLY in the sample. Be specific to THIS corpus — if it is about
medical imaging, say medical imaging; if automotive radar, say automotive radar. Do NOT default
to spectrum/RF unless the corpus is clearly about it.

Return JSON:
{{
  "domain": "concise domain label, 3-8 words",
  "domain_description": "one sentence scoping the domain and its boundaries",
  "system": "the system-under-analysis whose technology future we study, as a noun phrase, e.g. 'a <domain> system'",
  "horizon": "a sensible analysis horizon year for this domain, e.g. '2035'",
  "actor": "the organisation type whose strategy this foresight informs (a representative vendor/operator); name a real company ONLY if the corpus clearly centres on it",
  "actor_role": "short role description of that actor",
  "competitors": ["3-6 plausible competitor or peer organisations in this domain"],
  "forcing_functions": [{{"name": "a dominant external force (regulation, standard, market shift, geopolitics)", "description": "one line on how it forces the domain"}}],
  "function_examples": "comma-separated list of 6-8 core TECHNICAL FUNCTIONS any system in this domain must perform (seeds the morphological field)",
  "direction_good_example": "a GOOD example of 2-3 genuinely COMPETING technical directions for ONE function in this domain — pipe-separated, each quoted",
  "direction_bad_example": "a BAD example for the same function — mere performance levels (forbidden) — pipe-separated, each quoted",
  "manifestation_example": "2-3 lines: example of specific, distinct future end-states for one driver in this domain (not generic 'breakthrough/stagnation')",
  "cib_inhibit_examples": "2-3 short bullet calibration examples of one technology INHIBITING another in this domain, each with a one-line technical reason",
  "retrieval_queries": {{
    "functions": "search query to retrieve technical-function material",
    "directions": "query for competing approaches / paradigms / architectures",
    "trends": "query for technology trends in this domain",
    "bom": "query for the system's components / building blocks",
    "drivers": "query for external drivers (regulation, market, geopolitics)"
  }},
  "source_chunk_ids_used": ["chunk ids you relied on"]
}}"""


DOMAIN_PERSONAS = """Design an expert panel for a cross-impact / cross-consistency assessment in the domain
below. Each persona judges how two technologies in this domain interact, from a genuinely
different professional viewpoint.

DOMAIN: {domain}
DESCRIPTION: {domain_description}

Requirements:
- Exactly 5 personas, each a distinct lens. Include: a hands-on systems/engineering expert; a
  standards/regulatory or compliance analyst; an R&D portfolio / commercial strategist; an
  academic/research expert; AND one DISRUPTION & CONFLICT analyst whose explicit job is to find
  the tensions, resource conflicts and architectural incompatibilities the others miss.
- Each persona's system prompt MUST state concrete SCORING TENDENCIES (when they see genuine
  synergy vs. when they see conflict/competition), so the panel produces natural score spread
  rather than uniform positivity. Make the disruption analyst the strongest "find conflict" voice.
- 4-8 sentences each, specific to THIS domain, not generic.

Return JSON:
{{
  "personas": [
    {{"id": "snake_case_id", "name": "Role Name", "system": "system prompt with explicit scoring tendencies"}}
  ]
}}"""
