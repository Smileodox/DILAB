CIB_EVALUATE = """You are evaluating the cross-impact between two technology drivers in the regulatory frequency monitoring domain, looking ahead to 2035.

Driver A: {driver_a_name} — {driver_a_description}
Driver B: {driver_b_name} — {driver_b_description}

CONTEXT: Evaluate these interactions looking ahead to 2035. The ITU SM.2542 (2024) next-generation monitoring framework — which mandates autonomous, proactive, data-driven spectrum monitoring — is the key regulatory forcing function. Where either driver relates to autonomy, AI/ML, real-time processing, or standardisation, explicitly consider whether SM.2542 requirements enable or constrain that driver.

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
- Wideband Direct RF Sampling INHIBITS Analog Superheterodyne Channelizer (score: 2-3)
  → Functional overlap: both solve the same front-end problem. Investing in direct sampling
    reduces the need for analog downconversion. Same R&D budget, same board space.
- Regulatory Fragmentation INHIBITS AI-Based Autonomous Monitoring (score: 2)
  → Certification barriers multiply per jurisdiction. AI models trained on one regime's
    rules don't transfer to another. Development cost scales with regulatory diversity.
- Photonic ADC Development INHIBITS GaAs Mixer Investment (score: 2-3)
  → Architectural conflict: photonic front-ends bypass the analog mixing stage entirely.
    Success in photonic ADCs makes GaAs mixer improvements strategically irrelevant.

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
