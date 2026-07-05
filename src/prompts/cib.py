CIB_EVALUATE = """You are evaluating the cross-impact between two technology drivers in the {domain} domain, looking ahead to {horizon}.

Driver A: {driver_a_name} — {driver_a_description}
Driver B: {driver_b_name} — {driver_b_description}

CONTEXT: Evaluate these interactions looking ahead to {horizon}. {forcing_context}

STEP 1 — ANALYZE THE RELATIONSHIP:
Think carefully about the SPECIFIC relationship between A and B from your professional perspective:
- Is there a direct data/signal flow from A to B?
- Do they share the same hardware platform or processing pipeline?
- Do they compete for the same function or solve the same problem differently?
- Are they in entirely different subsystems with no dependency?

STEP 2 — SCORE THE INHIBITING EFFECT (0-3):
Spot conflicts and competition FIRST — this is the harder judgment and must be done before assessing synergies.
Consider ALL of these inhibition mechanisms — any one alone is sufficient:
(a) Functional overlap: A replaces or reduces the need for B.
(b) Resource competition: A and B compete for the same engineering team, R&D budget, hardware slot, or development priority. Investing in A means NOT investing in B.
(c) Architectural conflict: A pushes the system design in a direction that makes B harder to integrate.

DEFAULT RULE: If A and B are both in scope for the same product line, serve the same customer segment, or compete for the same R&D budget, start from inhibiting=1 and require a specific reason to score lower. Inhibiting=0 requires you to explicitly confirm that none of (a), (b), or (c) apply.

- 0 = Confirmed: no functional overlap, no shared resources, no architectural conflict. Justify explicitly.
- 1 = Mild tension on one dimension.
- 2 = Significant competition on at least one dimension.
- 3 = Direct replacement or fundamental architectural incompatibility.

TEST: "Does A's success make B less needed, less funded, or harder to integrate?" If ANY of the three applies → inhibiting is at least 1.

EXAMPLES OF INHIBITING RELATIONSHIPS (for calibration):
{cib_inhibit_examples}

STEP 3 — SCORE THE PROMOTING EFFECT (0-3):
Apply these gates strictly — each level requires a harder test:
- 0 = No dependency. A and B operate in separate subsystems. Progress in A does not change B's development path.
- 1 = Indirect benefit. A creates a slightly better environment for B, but B could succeed fully without A.
- 2 = Direct enablement. A produces outputs, data, or infrastructure that B specifically consumes. B would develop SLOWER without A.
- 3 = Critical prerequisite. B fundamentally CANNOT work without A.

TEST: "Could B achieve its goals if A made NO progress?" If yes → promoting is 0 or 1, not 2 or 3.

SOURCE MATERIAL:
{rag_chunks}

Return JSON (keep reasoning fields to 1-2 sentences max):
{{
  "relationship_analysis": "1 sentence: specific relationship between A and B",
  "inhibiting_score": (integer 0-3),
  "inhibiting_reasoning": "1 sentence: conflict mechanism or 'no conflict'",
  "promoting_score": (integer 0-3),
  "promoting_reasoning": "1 sentence: mechanism or 'no dependency'",
  "source_chunk_ids_used": ["chunk_id_1"]
}}"""


CIB_EVALUATE_CONTRASTIVE = """De-biased cross-impact assessment for a morphological scenario analysis in {domain} (horizon {horizon}). Weigh competition and enablement with EQUAL rigor — prime neither direction.

Driver A: {driver_a_name} — {driver_a_description}
Driver B: {driver_b_name} — {driver_b_description}

CONTEXT: Evaluate looking ahead to {horizon}. {forcing_context}

Two drivers in the same domain can relate in TWO opposite ways, and you must weigh both honestly, without assuming either is more likely:
- They can COMPETE — each is a committing bet claiming finite, shared resources (R&D budget, engineering focus, board/rack space, power & thermal budget, data bandwidth, roadmap and standardization priority), or one displaces the other's function. This is inhibition.
- They can ENABLE — one produces data, infrastructure, or momentum the other specifically consumes or benefits from. This is promotion.

Calibration warning (BOTH directions): language models tend to over-report synergy ("almost anything CAN be combined") — resist that reflex — but do NOT over-correct into blanket antagonism. Score what is actually there.

STEP 1 — SCORE INHIBITION (0-3), the competition / substitution side:
(a) Functional substitution: A's success reduces the need for B.
(b) Resource competition: investing in A means NOT investing in B (same budget, team, board slot, roadmap priority).
(c) Architectural conflict: A pushes the design in a direction that makes B harder to integrate.
  0 = none of (a)/(b)/(c) apply (say so)   1 = mild tension on one dimension
  2 = significant competition on at least one   3 = direct displacement / architectural incompatibility

STEP 2 — SCORE PROMOTION (0-3), the enablement side:
  0 = no dependency   1 = indirect benefit, B could succeed fully without A
  2 = direct enablement, B develops SLOWER without A   3 = A is a hard prerequisite; B cannot work without A
"An engineer COULD make both work" is NOT enablement — award >= 2 ONLY when A's outputs/data/infrastructure are specifically consumed by B.

HONESTY RULES (symmetric — neither thumb on the scale):
- Do NOT inflate promotion to paper over a genuine conflict.
- Do NOT invent conflict where the drivers are genuinely independent — then score both low, net ~0.
- Judge on TECHNICAL and resource logic only (data flow, architecture, physics, budget/board/roadmap contention), NOT regulation or policy.

SOURCE MATERIAL:
{rag_chunks}

CALIBRATION EXAMPLES OF INHIBITING RELATIONSHIPS:
{cib_inhibit_examples}

Return JSON (keep reasoning fields to 1-2 sentences max):
{{
  "relationship_analysis": "1 sentence: do A and B mainly compete, mainly enable, or neither, and why",
  "inhibiting_score": (integer 0-3),
  "inhibiting_reasoning": "1 sentence: the conflict/competition mechanism, or 'no conflict'",
  "promoting_score": (integer 0-3),
  "promoting_reasoning": "1 sentence: the enablement mechanism, or 'no dependency'",
  "source_chunk_ids_used": ["chunk_id_1"]
}}"""
