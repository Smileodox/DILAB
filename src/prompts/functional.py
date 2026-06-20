"""Prompts for functional morphological analysis (Zwicky).

Drivers = technical FUNCTIONS; manifestations = COMPETING DIRECTIONS (paradigms), not
optimistic→pessimistic quality levels. Consistency = Cross-Consistency Assessment over
direction pairs. This replaces the BOM-component + optimism-ladder extraction, which
produces only complementary capability sliders (no trade-offs → no scenario structure).
"""

FUNCTION_EXTRACT = """You are setting up a morphological scenario analysis for the FUTURE OF TECHNOLOGY
in regulatory frequency (spectrum) monitoring, horizon 2035.

Identify the core TECHNICAL FUNCTIONS that ANY spectrum-monitoring system must perform —
the functional building blocks, independent of today's specific products. These become the
orthogonal dimensions of a morphological field.

Based ONLY on the source material, list 6-9 core technical functions. Each must be:
- A capability the system must deliver (e.g. sense RF energy, digitize the spectrum,
  detect & classify signals, locate emitters, move/route data, run intelligence, integrate
  hardware).
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


DIRECTIONS_EXTRACT = """For the technical function below in spectrum monitoring (horizon 2035), identify 2-4
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
- Each must be a plausible, source-grounded direction under active research toward 2035.

GOOD example (function "where computation happens"):
  "Centralized cloud processing" | "On-sensor edge processing" | "Federated distributed processing"
BAD example (these are levels, NOT directions — forbidden):
  "high compute" | "medium compute" | "low compute"

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
(spectrum monitoring, horizon 2035). Score how technically compatible the approaches of two
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
