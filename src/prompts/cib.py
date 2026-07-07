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
