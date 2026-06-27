"""Prompts for functional morphological analysis (Zwicky).

Drivers = technical FUNCTIONS; manifestations = COMPETING DIRECTIONS (paradigms), not
optimistic→pessimistic quality levels. Consistency = Cross-Consistency Assessment over
direction pairs. This replaces the BOM-component + optimism-ladder extraction, which
produces only complementary capability sliders (no trade-offs → no scenario structure).
"""

FUNCTION_EXTRACT = """You are setting up a morphological scenario analysis for the FUTURE OF TECHNOLOGY
in {domain}, horizon {horizon}.

Identify the core TECHNICAL FUNCTIONS that any system in {domain} must perform —
the functional building blocks, independent of today's specific products. These become the
orthogonal dimensions of a morphological field.

Based ONLY on the source material, list 6-9 core technical functions. Each must be:
- A capability the system must deliver (e.g. {function_examples}).
- TECHNOLOGY-oriented — NOT regulatory, legal, or organizational.
- Distinct and non-overlapping from the others.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "functions": [
    {{"name": "short function name (max 6 words)", "description": "what this function does, 1-2 sentences"}}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


DIRECTIONS_EXTRACT = """For the technical function below in {domain} (horizon {horizon}), identify 2-4
COMPETING technological approaches — genuinely different DIRECTIONS the field could take to
fulfil this function.

FUNCTION: {function_name}
DESCRIPTION: {function_description}

SOURCE MATERIAL:
{rag_chunks}

CRITICAL RULES:
- These are competing PARADIGMS / ARCHITECTURES, NOT performance levels. NOT
  "advanced vs incremental vs stagnation", NOT "fast vs slow" — but genuinely different
  technical bets that are MUTUALLY EXCLUSIVE (a system commits largely to one of them).
- Choosing one tends to DISPLACE the others (they compete for the same role, budget, board
  space, or architecture).
- Each must be a plausible, source-grounded direction under active research toward {horizon}.

GOOD example of genuinely competing directions for one function:
  {direction_good_example}
BAD example (these are levels, NOT directions — forbidden):
  {direction_bad_example}

Return JSON:
{{
  "directions": [
    {{"label": "short distinctive name (max 8 words)",
      "description": "2-3 sentences: the approach and what it commits to / trades away",
      "plausibility": "high" or "medium" or "low"}}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""


CCA_FUNCTION_PAIR = """Cross-Consistency Assessment for a morphological scenario analysis
({domain}, horizon {horizon}). Score how technically compatible the approaches of two
different functions are, if a single system committed to BOTH.

FUNCTION A — {function_a_name}:
{directions_a}

FUNCTION B — {function_b_name}:
{directions_b}

For EVERY (A_i, B_j) combination, judge technical compatibility on this scale:
  +2  strong synergy — each enables or reinforces the other
  +1  mild synergy
   0  neutral / independent
  -1  tension — awkward or costly to combine
  -2  incompatible — architecturally contradictory; a system cannot sensibly do both

Base this on TECHNICAL logic only — data flow, architecture, physics, resource/budget/board
conflict. NOT on regulation or policy. Most pairs are 0; reserve ±2 for genuine cases.

Return JSON:
{{
  "pairs": [
    {{"a": <A index, 0-based>, "b": <B index, 0-based>, "score": -2, "reason": "short technical reason"}}
  ]
}}"""


CCA_FUNCTION_PAIR_CONTRASTIVE = """Cross-Consistency Assessment for a morphological scenario analysis
({domain}, horizon {horizon}), elicited by FORCED CONTRAST to expose architectural tension.

FUNCTION A — {function_a_name}:
{directions_a}

FUNCTION B — {function_b_name}:
{directions_b}

Each direction is a COMMITTING architectural bet: it claims finite, shared system resources
(power & thermal budget, board/rack space, data bandwidth, latency budget, capital, engineering
focus) and embodies a design philosophy (centralize vs distribute, raw-data vs reduced-data,
deterministic vs learned, fixed vs mobile). A single coherent system cannot lean every way at once.

Judge each (A_i, B_j) by ONE question: would a single COHERENT architecture naturally commit to
BOTH directions, or do they pull the system design in opposite directions?
  +2  co-designed — each direction technically requires or amplifies the other
  +1  comfortable together
   0  independent — no real interaction
  -1  tension — competes for the same resource, or embodies an opposing design philosophy
  -2  contradictory — committing to both means building two systems that fight each other

CRITICAL — avoid the "everything is mildly synergistic" trap:
- The default for two strong, committing bets is TENSION (-1), not synergy. "An engineer COULD
  make both work" is NOT synergy — almost anything can be bolted together. Award positive ONLY
  when one direction genuinely needs or reinforces the other.
- Your scores across these combinations MUST spread — rank them internally from most-incompatible
  to most-synergistic. A flat or all-positive answer is INVALID: it means you have not found the
  real tension. Name the single most-incompatible combination explicitly.
- Do NOT invent conflicts: if two directions truly are independent, score 0. Honesty over drama.
- TECHNICAL logic only (data flow, physics, resource/architecture conflict), NOT regulation/policy.

Return JSON:
{{
  "most_incompatible": {{"a": <A index>, "b": <B index>, "reason": "short technical reason"}},
  "pairs": [
    {{"a": <A index, 0-based>, "b": <B index, 0-based>, "score": -2, "reason": "short technical reason"}}
  ]
}}"""
