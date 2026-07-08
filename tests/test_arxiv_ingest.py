"""Offline tests for the arXiv ingester: pure Atom parser, query builder, and KB mapping.

No network and no Azure: the parser runs on a fixture feed, and ingest uses a fake collection
+ injected embedding fn. Verifies the traceability contract (source_id + year in metadata).
"""
from src.models.common import KBPool, stable_id
from src.pipeline.arxiv_ingest import build_query, ingest_papers, parse_arxiv_atom

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <published>2024-01-20T10:00:00Z</published>
    <title>Deep Learning for
      Spectrum Sensing</title>
    <summary>  We propose a neural approach to wideband spectrum sensing that improves
    detection at low SNR by a large margin across many frequency bands.  </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link href="http://arxiv.org/abs/2401.01234v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.01234v1" rel="related" type="application/pdf"/>
    <category term="eess.SP" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.55555v2</id>
    <published>2025-02-01T00:00:00Z</published>
    <title>Short</title>
    <summary>Too short.</summary>
    <author><name>Carol Ng</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2402.55555v2"/>
    <category term="cs.NI"/>
  </entry>
</feed>"""


class TestBuildQuery:
    def test_terms_only(self):
        assert build_query("spectrum monitoring") == "all:spectrum monitoring"

    def test_terms_and_categories(self):
        assert build_query("spectrum", ["cs.NI", "eess.SP"]) == \
            "(all:spectrum) AND (cat:cs.NI OR cat:eess.SP)"

    def test_categories_only(self):
        assert build_query("", ["cs.NI"]) == "(cat:cs.NI)"


class TestParseAtom:
    def test_fields_and_normalization(self):
        papers = parse_arxiv_atom(FEED)
        assert len(papers) == 2
        p = papers[0]
        assert p["arxiv_id"] == "2401.01234v1"
        assert p["title"] == "Deep Learning for Spectrum Sensing"   # whitespace normalized
        assert p["abstract"].startswith("We propose a neural approach")
        assert "  " not in p["abstract"]                            # collapsed
        assert p["year"] == "2024"
        assert p["authors"] == ["Alice Smith", "Bob Jones"]
        assert p["categories"] == ["eess.SP", "cs.LG"]
        assert p["pdf_url"] == "http://arxiv.org/pdf/2401.01234v1"
        assert papers[1]["year"] == "2025" and papers[1]["arxiv_id"] == "2402.55555v2"


class _FakeCollection:
    def __init__(self):
        self.added = []

    def add(self, ids, embeddings, documents, metadatas):
        assert len(ids) == len(embeddings) == len(documents) == len(metadatas)
        self.added.append({"ids": ids, "metadatas": metadatas, "documents": documents})


class TestIngestMapping:
    def test_ingest_preserves_traceability_and_skips_short(self):
        papers = parse_arxiv_atom(FEED)
        coll = _FakeCollection()
        fake_embed = lambda texts: [[0.0, 0.1, 0.2] for _ in texts]  # noqa: E731
        res = ingest_papers(papers, collection=coll, embed_fn=fake_embed)

        # The short-abstract paper yields no usable chunk -> skipped.
        assert res["skipped"] == ["2402.55555v2"]
        assert res["n_chunks"] == 1

        sid = stable_id("arxiv", "2401.01234v1")
        chunk = next(iter(res["chunks"].values()))
        assert chunk.source_id == sid                     # driver->source traceability intact
        assert res["sources"][sid].type.value == "research_paper"
        assert res["sources"][sid].content_origin.value == "fetched"

        meta = coll.added[0]["metadatas"][0]
        assert meta["source_id"] == sid                   # temporal.py breadth signal
        assert meta["year"] == "2024"                     # temporal.py recency signal
        assert meta["pool"] == KBPool.TREND.value
        assert meta["publisher"] == "arXiv"
