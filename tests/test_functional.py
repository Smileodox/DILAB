from src.models.morphological import DriverManifestation, MorphologicalBox
from src.pipeline import functional
from src.pipeline.functional import (
    CCA_PROMPTS,
    assess_cca,
    cca_contradiction,
    sample_consistent,
)
from src.prompts.functional import CCA_FUNCTION_PAIR, CCA_FUNCTION_PAIR_CONTRASTIVE


def _box():
    specs = {"A": ["a1", "a2"], "B": ["b1", "b2"], "C": ["c1", "c2"]}
    drivers, manifs, allm, lab = [], {}, [], {}
    for fn, dirs in specs.items():
        fid = "f_" + fn
        drivers.append(fid)
        manifs[fid] = []
        for d in dirs:
            m = DriverManifestation(driver_id=fid, label=d, description=d, plausibility="medium")
            manifs[fid].append(m.id)
            allm.append(m)
            lab[d] = m.id
    return MorphologicalBox(drivers=drivers, manifestations=manifs, all_manifestations=allm), lab


def _cca(lab, raw):
    cca = {}
    for (x, y), s in raw.items():
        cca.setdefault(lab[x], {})[lab[y]] = s
        cca.setdefault(lab[y], {})[lab[x]] = s
    return cca


class TestCcaContradiction:
    def test_no_edges_is_zero(self):
        box, lab = _box()
        cfg = {d: box.manifestations[d][0] for d in box.drivers}
        ratio, hard, net = cca_contradiction(cfg, box, {})
        assert ratio == 0.0 and not hard and net == 0

    def test_hard_incompatibility_flagged(self):
        box, lab = _box()
        cca = _cca(lab, {("a1", "b1"): -2})
        cfg = {"f_A": lab["a1"], "f_B": lab["b1"], "f_C": lab["c1"]}
        ratio, hard, net = cca_contradiction(cfg, box, cca)
        assert hard and net == -2 and 0.0 < ratio <= 1.0

    def test_synergy_net_positive_no_tension(self):
        box, lab = _box()
        cca = _cca(lab, {("a1", "b1"): 2, ("a1", "c1"): 1})
        cfg = {"f_A": lab["a1"], "f_B": lab["b1"], "f_C": lab["c1"]}
        ratio, hard, net = cca_contradiction(cfg, box, cca)
        assert net == 3 and not hard and ratio == 0.0


class TestCcaMode:
    def test_prompt_registry(self):
        assert CCA_PROMPTS["absolute"] is CCA_FUNCTION_PAIR
        assert CCA_PROMPTS["contrastive"] is CCA_FUNCTION_PAIR_CONTRASTIVE
        assert "FORCED CONTRAST" in CCA_FUNCTION_PAIR_CONTRASTIVE
        assert "FORCED CONTRAST" not in CCA_FUNCTION_PAIR

    def _run_capture(self, monkeypatch, mode):
        box, lab = _box()
        manif_by_id = {m.id: m for m in box.all_manifestations}
        name_by_fid = {d: d for d in box.drivers}
        seen = []

        def fake(prompt, temperature=0.1, model=None):
            seen.append(prompt)
            return {"pairs": [{"a": 0, "b": 0, "score": -2}]}

        monkeypatch.setattr(functional, "safe_chat_json", fake)
        cca = assess_cca(box, manif_by_id, name_by_fid, mode=mode, max_workers=2)
        return cca, seen

    def test_contrastive_uses_contrastive_prompt(self, monkeypatch):
        cca, seen = self._run_capture(monkeypatch, "contrastive")
        assert seen and all("FORCED CONTRAST" in p for p in seen)
        assert cca  # scores were written symmetrically

    def test_absolute_uses_absolute_prompt(self, monkeypatch):
        _, seen = self._run_capture(monkeypatch, "absolute")
        assert seen and all("FORCED CONTRAST" not in p for p in seen)

    def test_unknown_mode_falls_back_to_absolute(self, monkeypatch):
        _, seen = self._run_capture(monkeypatch, "nonsense")
        assert seen and all("FORCED CONTRAST" not in p for p in seen)


class TestSampleConsistent:
    def test_drops_hard_incompatible(self):
        box, lab = _box()
        cca = _cca(lab, {("a1", "b1"): -2})  # a1 + b1 may never co-occur
        res = sample_consistent(box, cca, n_samples=8, oversample_factor=20.0, reject_threshold=1.0, seed=1)
        assert res
        for c in res:
            assert not (c.configuration["f_A"] == lab["a1"] and c.configuration["f_B"] == lab["b1"])

    def test_deterministic_with_seed(self):
        box, lab = _box()
        cca = _cca(lab, {("a1", "b2"): 1})
        a = sample_consistent(box, cca, n_samples=5, reject_threshold=1.0, seed=7)
        b = sample_consistent(box, cca, n_samples=5, reject_threshold=1.0, seed=7)
        assert [c.configuration for c in a] == [c.configuration for c in b]

    def test_covers_all_drivers_not_fixed_point(self):
        box, lab = _box()
        res = sample_consistent(box, {}, n_samples=6, reject_threshold=1.0, seed=1)
        assert res
        for c in res:
            assert set(c.configuration.keys()) == set(box.drivers)
            assert not c.is_fixed_point and c.is_consistent
