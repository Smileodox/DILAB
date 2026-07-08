"""Offline tests for the temporal / DVI-lineage driver profile (pure `temporal_stats`)."""
from src.pipeline.temporal import temporal_stats

# corpus median = 2015.0 (n=6, distinct=6, span=10 -> has_temporal_signal True)
CORPUS = [2010, 2012, 2014, 2016, 2018, 2020]


def _by_id(res):
    return {d["driver_id"]: d for d in res["drivers"]}


class TestHonestyGate:
    def test_thin_corpus_yields_insufficient_verdict(self):
        res = temporal_stats({"a": [2019, 2020, 2021]}, [2020, 2020])  # distinct=1
        assert res["has_temporal_signal"] is False
        assert res["verdict"] == "insufficient temporal evidence"
        a = _by_id(res)["a"]
        assert a["emergence"] == "unknown"
        assert a["recency_shift"] is None
        assert a["visibility_trend"] == "unknown"

    def test_driver_below_min_dated_stays_unknown_even_with_signal(self):
        res = temporal_stats({"thin": [2020]}, CORPUS, driver_sources={"thin": ["s1"]})
        assert res["has_temporal_signal"] is True
        thin = _by_id(res)["thin"]
        assert thin["emergence"] == "unknown"          # n=1 < min_driver_dated
        assert thin["visibility_trend"] == "unknown"
        assert thin["diffusion"] == "narrow"           # breadth is independent of temporal gate


class TestLevelAndSlope:
    def test_emerging_rising(self):
        res = temporal_stats({"a": [2019, 2020, 2021]}, CORPUS)
        a = _by_id(res)["a"]
        assert a["emergence"] == "emerging"
        assert a["recency_shift"] == 5.0
        assert a["visibility_trend"] == "rising"

    def test_established_waning(self):
        res = temporal_stats({"b": [2008, 2010, 2019]}, CORPUS)  # median 2010
        b = _by_id(res)["b"]
        assert b["emergence"] == "established"
        assert b["visibility_trend"] == "waning"       # 1 recent (2019) < 2 older

    def test_steady(self):
        res = temporal_stats({"c": [2014, 2015, 2016]}, CORPUS)  # median 2015 == corpus
        assert _by_id(res)["c"]["emergence"] == "steady"


class TestDiffusion:
    def test_breadth_buckets(self):
        srcs = {"broad": ["s1", "s2", "s3", "s4"], "mod": ["s1", "s2"], "narrow": ["s1", "s1"]}
        years = {k: [2019, 2020] for k in srcs}
        res = _by_id(temporal_stats(years, CORPUS, driver_sources=srcs))
        assert res["broad"]["diffusion"] == "broad" and res["broad"]["n_sources"] == 4
        assert res["mod"]["diffusion"] == "moderate" and res["mod"]["n_sources"] == 2
        assert res["narrow"]["diffusion"] == "narrow" and res["narrow"]["n_sources"] == 1

    def test_unknown_when_sources_omitted(self):
        res = _by_id(temporal_stats({"a": [2019, 2020]}, CORPUS))
        assert res["a"]["diffusion"] == "unknown"
        assert res["a"]["n_sources"] is None


class TestWeakSignal:
    def test_emerging_thin_narrow_is_weak(self):
        res = temporal_stats({"a": [2019, 2020, 2021]}, CORPUS, driver_sources={"a": ["s1"]})
        assert _by_id(res)["a"]["is_weak_signal"] is True

    def test_emerging_thin_but_broad_is_not_weak(self):
        res = temporal_stats({"a": [2019, 2020, 2021]}, CORPUS,
                             driver_sources={"a": ["s1", "s2", "s3"]})
        assert _by_id(res)["a"]["is_weak_signal"] is False   # broadly sourced -> not "weak"

    def test_established_is_not_weak(self):
        res = temporal_stats({"b": [2008, 2010, 2011]}, CORPUS, driver_sources={"b": ["s1"]})
        assert _by_id(res)["b"]["is_weak_signal"] is False

    def test_backward_compat_without_sources(self):
        # No driver_sources -> diffusion "unknown" (!= "broad") -> classic emerging+thin weak signal.
        res = temporal_stats({"a": [2019, 2020, 2021]}, CORPUS)
        assert _by_id(res)["a"]["is_weak_signal"] is True
