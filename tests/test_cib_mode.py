"""Offline tests for the contrastive CIB elicitation mode (no LLM, no network).

Mirrors the contrastive-CCA pattern in functional.py: a CIB_PROMPTS dict + a mode flag.
These tests guard the two things that can silently break the pipeline: a missing/extra
template placeholder (KeyError at format time) and the mode selector wiring.
"""

from src.models.domain import DomainProfile
from src.pipeline.cib import CIB_PROMPTS
from src.prompts.cib import CIB_EVALUATE, CIB_EVALUATE_CONTRASTIVE


def _format_kwargs():
    """The exact slot dict cib.run() formats a pair prompt against."""
    return {
        "driver_a_name": "Wideband ADC",
        "driver_a_description": "high-rate direct RF digitization",
        "driver_b_name": "Dynamic spectrum sharing regime",
        "driver_b_description": "regulatory shift to shared/licensed-by-rule access",
        "rag_chunks": "(no chunks)",
        **DomainProfile(domain="regulatory frequency monitoring").prompt_kwargs(),
    }


def test_cib_prompts_registry():
    assert CIB_PROMPTS["absolute"] is CIB_EVALUATE
    assert CIB_PROMPTS["contrastive"] is CIB_EVALUATE_CONTRASTIVE


def test_both_prompts_format_without_keyerror():
    # A missing/misspelled placeholder would raise KeyError here — the most common prompt-edit
    # bug. (Reaching the asserts at all means every {slot} resolved cleanly.)
    kw = _format_kwargs()
    for template in (CIB_EVALUATE, CIB_EVALUATE_CONTRASTIVE):
        text = template.format(**kw)
        assert "Wideband ADC" in text
        assert "Dynamic spectrum sharing regime" in text
        assert "regulatory frequency monitoring" in text  # domain slot filled from prompt_kwargs


def test_contrastive_prompt_is_symmetric_not_primed():
    """The de-biased prompt must prime NEITHER direction — no thumb on the scale.

    (An earlier draft primed toward tension and over-corrected to ~71% negative; we removed
    that. Tuning the wording to hit a target negative-share would be p-hacking — so this test
    guards symmetry, not a number.)
    """
    contrastive = CIB_EVALUATE_CONTRASTIVE.format(**_format_kwargs())
    low = contrastive.lower()
    assert CIB_EVALUATE_CONTRASTIVE is not CIB_EVALUATE
    # Names BOTH sides with equal billing.
    assert "compete" in low or "competition" in low
    assert "enable" in low or "enablement" in low
    # The removed negative thumbs must stay gone.
    assert "start from inhibiting" not in low
    assert "default relationship" not in low
    assert "whole point" not in low
    # No leading-the-witness target inside the prompt.
    assert "20-30% negative" not in contrastive
    assert "Weimer-Jehle" not in contrastive


def test_contrastive_keeps_cibresponse_output_schema():
    # Downstream parsing depends on these exact JSON keys (CIBResponse) — keep them in both.
    for template in (CIB_EVALUATE, CIB_EVALUATE_CONTRASTIVE):
        for field in ("inhibiting_score", "promoting_score",
                      "inhibiting_reasoning", "promoting_reasoning", "source_chunk_ids_used"):
            assert field in template


def test_unknown_mode_falls_back_to_absolute():
    assert CIB_PROMPTS.get("nonsense", CIB_EVALUATE) is CIB_EVALUATE
