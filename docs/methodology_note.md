# Methodology Note: Bottom-Up vs. Top-Down Foresight with LLMs

## The Problem

Strategic technology foresight aims to identify developments that could disrupt an organization's business within a 5-10 year horizon. The hardest part is not analyzing known trends — it is discovering **blind spots**: developments the organization is not yet tracking.

LLMs offer two capabilities relevant to this problem:
1. **Retrieval-augmented extraction** — grounding claims in verifiable sources
2. **Creative cross-domain reasoning** — connecting ideas across fields that domain experts rarely bridge

The challenge is exploiting (2) without sacrificing the traceability that (1) provides.

## Bottom-Up: Corpus-Driven Discovery (poc2c)

**Pipeline:** Corpus &rarr; Retrieval &rarr; Driver Extraction &rarr; Faithfulness Check &rarr; Surprise Assessment

The bottom-up approach starts from a document corpus (academic papers via OpenAlex, expanded through citation graph traversal). An LLM extracts technology drivers from retrieved chunks, each grounded in verbatim source quotes. A RAGAS-style faithfulness check decomposes each driver description into atomic claims and verifies them against source evidence. Finally, a surprise assessment rates how likely the organization already tracks each driver.

**Strengths:**
- Every claim is traceable to a specific source passage
- Faithfulness scores provide quantitative grounding quality
- Full audit trail: query &rarr; paper &rarr; chunk &rarr; claim &rarr; verdict

**Weakness discovered (poc2c result):**
Citation graphs cluster around established research communities. Of 22 extracted drivers, 21 were rated "known by R&S" and 100% fell in the Technological STEEP category. Aggressive prompting ("skip the obvious") cannot override what is in the retrieved chunks. **You cannot find the unknown by digging deeper into the known.**

## Top-Down: Hypothesis-First Discovery (poc2d)

**Pipeline:** LLM Hypothesis Generation &rarr; Evidence Search &rarr; Validation &rarr; Categorization

The top-down approach inverts the pipeline. Instead of extracting what the corpus contains, we use the LLM to generate disruption hypotheses using established foresight frameworks, then search for evidence to validate or falsify each hypothesis.

Five disruption frameworks structure the hypothesis generation:
1. **Christensen Disruption** — "good enough" technology undermining high-end incumbents from below
2. **Adjacent Possible** — combinations of existing technologies that become feasible only now
3. **Regulatory Shock** — policy changes that force market restructuring
4. **Platform Shift** — value chain migration (e.g., hardware to analytics-as-a-service)
5. **Convergence** — previously separate industries merging into a shared space

Each hypothesis is generated with concrete search queries, enabling automated evidence retrieval. The validation step reuses the same faithfulness infrastructure from poc2c.

**Three output categories:**
- **Validated** — Academic/patent evidence found, faithfulness score above threshold. Grounded and auditable.
- **Speculative** — No or insufficient evidence found. Transparently labeled as LLM-generated hypothesis without external support. Potentially the most interesting category: either a weak signal too new for academic literature, a cross-domain transfer nobody has studied, or a hallucination. The audit trail makes the distinction transparent.
- **Falsified** — Evidence actively contradicts the hypothesis. Also valuable for strategic planning.

**Strengths:**
- Reaches beyond the citation graph into cross-domain territory
- Disruption frameworks provide structured creative exploration, not open-ended generation
- Speculative drivers are first-class citizens, not failures
- Same audit trail as bottom-up (where evidence exists)

**Weakness:**
- The LLM's training data defines the hypothesis space — it cannot generate hypotheses about things it has never seen
- Quality depends heavily on framework prompts and domain context
- Risk of generic output ("AI disrupts everything") if prompts lack specificity

## Why Both Approaches Are Complementary

| Dimension | Bottom-Up (poc2c) | Top-Down (poc2d) |
|-----------|-------------------|------------------|
| Starting point | Document corpus | LLM reasoning + frameworks |
| Finds | What the literature says | What the literature might be missing |
| Grounding | Strong (every claim sourced) | Mixed (validated = strong, speculative = transparent gap) |
| Blind spot potential | Low (corpus-bounded) | High (framework-guided exploration) |
| Risk | Confirms the known | Generates plausible-sounding noise |

The ideal pipeline combines both: bottom-up for establishing the validated knowledge base, top-down for probing beyond its boundaries.

## Guiding Principle

> "Exploit LLM **capabilities**, not its **knowledge**."

The hypothesis-first approach uses the LLM's capability (structured creative reasoning across domains) without trusting its knowledge (all factual claims are externally validated or transparently marked as speculative).

## References

- Weimer-Jehle, W. (2006). Cross-Impact Balances: A System-Theoretical Approach to Cross-Impact Analysis. *Technological Forecasting and Social Change*, 73(4), 334-361.
- Christensen, C. M. (1997). *The Innovator's Dilemma*. Harvard Business Review Press.
- Kauffman, S. (2000). *Investigations*. Oxford University Press. (Adjacent Possible)
- Es, S. et al. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. *arXiv:2309.15217*.
- Halawi, D. et al. (2024). Approaching Human-Level Forecasting with Language Models. *NeurIPS 2024*.
- Lorenz, J. & Fritz, P. (2026). Scalable Delphi: LLM-Based Expert Panels. *arXiv:2602.08889*.
