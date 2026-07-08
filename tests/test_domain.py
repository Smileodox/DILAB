import importlib
import json
import string

import pytest

from src import config
from src.models.domain import DomainProfile, ForcingFunction, Persona
from src.pipeline import domain

# Prompt modules that must be fully domain-neutral (domain.py is exempt: it READS the KB and
# legitimately names example domains in its instructions).
PROMPT_MODULES = ["bom", "trends", "merge", "cib", "scenarios", "evaluation",
                  "morphological", "functional", "strategic_framing", "personas"]

# Terms that would betray a hardwired domain (the spectrum-monitoring test case).
BANNED = ["spectrum", "rohde", "schwarz", "keysight", "teledyne", "sm.2542",
          "regulatory frequency", "rf energy", "emitter", "2035"]


def _string_constants(module):
    out = []
    for nm in dir(module):
        if not nm.isupper():
            continue
        val = getattr(module, nm)
        if isinstance(val, str):
            out.append((nm, val))
        elif isinstance(val, dict):
            out += [(f"{nm}[{k}]", v) for k, v in val.items() if isinstance(v, str)]
    return out


class TestDomainProfile:
    def test_prompt_kwargs_complete_and_nonempty(self):
        kw = DomainProfile(domain="radio monitoring", actor="Acme").prompt_kwargs()
        assert kw["domain"] == "radio monitoring"
        assert all(v for v in kw.values()), "every slot must be non-empty"

    def test_sparse_profile_has_safe_fallbacks(self):
        kw = DomainProfile(domain="quantum sensing").prompt_kwargs()
        assert all(v for v in kw.values())
        assert "quantum sensing" in kw["system"]

    def test_forcing_context_uses_functions(self):
        p = DomainProfile(domain="x", forcing_functions=[ForcingFunction(name="GDPR", description="privacy")])
        assert "GDPR" in p.prompt_kwargs()["forcing_context"]

    def test_query_fallback(self):
        p = DomainProfile(domain="x", retrieval_queries={"functions": "q1"})
        assert p.query("functions", "fb") == "q1"
        assert p.query("missing", "fb") == "fb"


class TestPromptsAreDomainNeutral:
    def test_no_hardwired_domain_terms(self):
        offenders = []
        for mname in PROMPT_MODULES:
            mod = importlib.import_module(f"src.prompts.{mname}")
            for cname, text in _string_constants(mod):
                low = text.lower()
                for term in BANNED:
                    if term in low:
                        offenders.append(f"{mname}.{cname}: '{term}'")
        assert not offenders, "hardwired domain terms found:\n" + "\n".join(offenders)

    def test_every_prompt_slot_is_satisfiable(self):
        """Every {slot} in every prompt is either a profile slot or a known call kwarg."""
        slots = set(DomainProfile(domain="x").prompt_kwargs().keys())
        call_kwargs = {
            "rag_chunks", "chunks_text", "driver_name", "driver_description", "driver_origin",
            "driver_confidence", "driver_a_name", "driver_a_description", "driver_b_name",
            "driver_b_description", "function_name", "function_description", "function_a_name",
            "function_b_name", "directions_a", "directions_b", "driver_manifestations_block",
            "cib_context", "narrative_guide", "existing_titles_block", "scenario_type", "word_count",
            "anchor_drivers", "driver_assumptions", "perspective", "n", "scenarios_block",
            "trend_name", "trend_description", "parent_context", "component_name",
            "component_description", "name", "description", "bom_path", "bom_drivers",
            "trend_drivers", "kb_sample", "origin",
            # pointwise evidence-grounded auditor (SCENARIO_POINTWISE_EVIDENCE_ASSESS)
            "scenario_title", "scenario_perspective", "scenario_assumptions",
            "scenario_narrative", "evidence_block",
        }
        allowed = slots | call_kwargs
        unknown = []
        for mname in PROMPT_MODULES + ["domain"]:
            mod = importlib.import_module(f"src.prompts.{mname}")
            for cname, text in _string_constants(mod):
                fields = {fn for _, fn, _, _ in string.Formatter().parse(text) if fn}
                unknown += [f"{mname}.{cname}:{f}" for f in (fields - allowed)]
        assert not unknown, "prompt slots not covered by prompt_kwargs or a call kwarg:\n" + "\n".join(unknown)


class _FakeCollection:
    def get(self, limit=50, include=None):
        return {
            "ids": [f"c{i}" for i in range(3)],
            "documents": ["Doc about turbine blade fatigue and inspection.",
                          "Sensor networks for wind farm condition monitoring.",
                          "Predictive maintenance standards for rotating machinery."],
            "metadatas": [{"source_title": "src1"}, {"source_title": "src2"}, {"source_title": "src3"}],
        }


class TestDerivation:
    def _mock_llm(self):
        calls = {"n": 0}

        def fake(prompt, temperature=0.3, model=None):
            calls["n"] += 1
            if "expert panel" in prompt.lower() or "personas" in prompt.lower():
                return {"personas": [
                    {"id": "eng", "name": "Engineer", "system": "sys"},
                    {"id": "skeptic", "name": "Disruption Analyst", "system": "find conflict"},
                ]}
            return {
                "domain": "wind turbine condition monitoring",
                "domain_description": "monitoring rotating machinery health",
                "system": "a wind turbine condition monitoring system",
                "horizon": "2035",
                "actor": "a turbine OEM",
                "actor_role": "manufacturer",
                "competitors": ["Vendor A", "Vendor B"],
                "forcing_functions": [{"name": "IEC standards", "description": "safety"}],
                "function_examples": ["sense vibration", "detect cracks"],   # list → coerced
                "direction_good_example": '"a" | "b"',
                "cib_inhibit_examples": ["X inhibits Y because shared sensor bus"],
                "retrieval_queries": {"functions": "turbine functions"},
                "source_chunk_ids_used": ["c0", "c1"],
            }
        return fake

    def test_derive_builds_profile(self, monkeypatch):
        monkeypatch.setattr(domain, "safe_chat_json", self._mock_llm())
        p = domain.derive(_FakeCollection())
        assert p.domain == "wind turbine condition monitoring"
        assert isinstance(p.function_examples, str) and "vibration" in p.function_examples  # coerced
        assert "shared sensor bus" in p.cib_inhibit_examples
        assert [pe.id for pe in p.personas] == ["eng", "skeptic"]
        assert p.retrieval_queries["functions"] == "turbine functions"

    def test_config_overrides_win(self, monkeypatch):
        monkeypatch.setattr(domain, "safe_chat_json", self._mock_llm())
        monkeypatch.setattr(config, "DOMAIN_HORIZON", "2050")
        monkeypatch.setattr(config, "DOMAIN_ACTOR", "Acme Corp")
        p = domain.derive(_FakeCollection())
        assert p.horizon == "2050" and p.actor == "Acme Corp"

    def test_empty_kb_raises(self, monkeypatch):
        class Empty:
            def get(self, limit=50, include=None):
                return {"ids": [], "documents": [], "metadatas": []}
        with pytest.raises(RuntimeError):
            domain.derive(Empty())

    def test_load_profile_roundtrip(self, tmp_path):
        p = DomainProfile(domain="d", personas=[Persona(id="a", name="A", system="s")])
        path = tmp_path / "domain_profile.json"
        path.write_text(json.dumps(p.model_dump(mode="json")))
        loaded = domain.load_profile(str(path))
        assert loaded.domain == "d" and loaded.personas[0].id == "a"

    def test_load_profile_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            domain.load_profile(str(tmp_path / "nope.json"))
