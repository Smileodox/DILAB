"""Prompt for naming a scenario archetype (a dense cluster of the combinatorial field).

Domain-neutral: the only domain-specific slot is ``{domain}``; the archetype's identity comes
entirely from the distinguishing drivers ``{features}`` and example excerpts ``{narrative_block}``
supplied at call time. No domain taxonomy is hardwired here.
"""

CLUSTER_LABEL = """You are naming a recurring scenario ARCHETYPE for a technology-foresight study on {domain}.

A group of internally-similar scenarios shares these distinguishing characteristics
(driver -> the state that is over-represented in this group versus the rest of the field):
{features}
{narrative_block}
Give the archetype a short, evocative NAME and a crisp description of what defines it and how it
differs from the other archetypes. Do not restate the driver list verbatim; synthesize its meaning.

Return JSON:
{{"name": "a 3-6 word archetype name", "description": "2 sentences: what defines this archetype and what sets it apart"}}"""
