"""DomainProfile — the domain abstraction layer that makes the pipeline KB-agnostic.

Everything domain-specific (what field we analyse, the horizon, the actor whose strategy
we inform, the expert lenses, the calibration examples, the retrieval queries) is DERIVED
from the docked knowledge base into a ``DomainProfile`` and injected into otherwise
domain-neutral prompt templates via :meth:`DomainProfile.prompt_kwargs`. No domain term is
hardwired in a prompt anymore — dock a different KB, get a different profile, same pipeline.

``prompt_kwargs()`` is the single slot contract: every neutralized prompt formats against
these keys, and the helper guarantees a non-empty fallback for each so a sparse profile can
never raise ``KeyError``/blank a prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Persona(BaseModel):
    """One expert lens for the multi-perspective panel (CIB / CCA scoring)."""

    id: str
    name: str
    system: str
    model: str = "gpt-5.4"


class ForcingFunction(BaseModel):
    """A dominant external driver of the domain (regulatory mandate, market shift, …)."""

    name: str
    description: str = ""


class DomainProfile(BaseModel):
    """Domain context derived from a knowledge base; the source of all domain framing.

    Fields map 1:1 onto prompt slots (see :meth:`prompt_kwargs`). The ``*_example`` fields
    carry domain-appropriate calibration text that used to be hardwired into the prompts
    (e.g. the CIB "Wideband Direct RF Sampling INHIBITS …" examples).
    """

    domain: str                                  # "regulatory frequency monitoring"
    domain_description: str = ""                 # one-line scope of the domain
    system: str = ""                             # "a regulatory frequency monitoring system"
    horizon: str = "2035"                        # analysis horizon (overridable via config)
    actor: str = ""                              # "Rohde & Schwarz" — whose strategy we inform
    actor_role: str = ""                         # "a spectrum monitoring equipment manufacturer"
    competitors: list[str] = Field(default_factory=list)
    forcing_functions: list[ForcingFunction] = Field(default_factory=list)

    # Calibration examples (domain-specific text, derived — never hardwired in prompts).
    function_examples: str = ""                  # for functional FUNCTION_EXTRACT
    direction_good_example: str = ""             # GOOD example for DIRECTIONS_EXTRACT
    direction_bad_example: str = ""              # BAD (forbidden) example for DIRECTIONS_EXTRACT
    manifestation_example: str = ""              # for morphological MANIFESTATION_DETERMINE
    cib_inhibit_examples: str = ""               # calibration block for CIB_EVALUATE

    driver_types: str = "regulatory|market|technological|geopolitical|societal"
    personas: list[Persona] = Field(default_factory=list)
    retrieval_queries: dict[str, str] = Field(default_factory=dict)
    source_chunk_ids: list[str] = Field(default_factory=list)

    # --- prompt contract -------------------------------------------------------------

    def _forcing_context(self) -> str:
        if not self.forcing_functions:
            return ("Consider the dominant external forces (regulation, standards, market, "
                    "geopolitics) shaping this domain.")
        items = "; ".join(
            f"{f.name}" + (f" — {f.description}" if f.description else "")
            for f in self.forcing_functions
        )
        return ("Key external forcing functions shaping this domain: " + items +
                ". Where a driver relates to these, consider how they enable or constrain it.")

    def prompt_kwargs(self) -> dict[str, str]:
        """The slot dict every neutralized prompt formats against (with safe fallbacks)."""
        domain = self.domain or "this technology domain"
        return {
            "domain": domain,
            "domain_description": self.domain_description or domain,
            "system": self.system or f"a {domain} system",
            "horizon": self.horizon or "the analysis horizon",
            "actor": self.actor or "a leading vendor in this domain",
            "actor_role": self.actor_role or "a leading vendor in this domain",
            "competitors": ", ".join(self.competitors) if self.competitors else "established competitors",
            "forcing_context": self._forcing_context(),
            "function_examples": self.function_examples or "the core capabilities the system must deliver",
            "direction_good_example": self.direction_good_example
                or '"Centralized processing" | "On-device edge processing" | "Federated distributed processing"',
            "direction_bad_example": self.direction_bad_example
                or '"high capability" | "medium capability" | "low capability"',
            "manifestation_example": self.manifestation_example
                or "specific, source-grounded end states this driver could reach",
            "cib_inhibit_examples": self.cib_inhibit_examples
                or "(no domain calibration examples available — reason from first principles)",
            "driver_types": self.driver_types,
        }

    def query(self, key: str, fallback: str) -> str:
        """Retrieval query for an extraction step, derived from the domain (with fallback)."""
        return self.retrieval_queries.get(key) or fallback
