"""arXiv corpus ingestion — a domain-agnostic source expander for the knowledge base.

Harvested from the AdiTest branch's arXiv fetcher, but rebuilt to our contract: it maps each
paper into the SAME ``Source``/``Chunk`` shape and Chroma metadata (``source_id`` + ``year``)
that ``kb.ingest`` writes, so drivers stay traceable (``source_chunk_ids``) and the temporal
profile (``temporal.py``) gets dated, spread-out literature to work with.

Domain-neutral by construction: the search query comes from the caller (or a derived
``DomainProfile``), and the arXiv category filter is an OPTIONAL parameter — nothing about a
specific domain (spectrum, telecom, …) is hardwired here. Uses only the standard library for
fetching (``urllib``), so no new dependency is added.

``build_query`` and ``parse_arxiv_atom`` are pure → fully unit-testable offline; ``fetch_arxiv``
is the thin network layer; ``ingest_papers`` embeds into Chroma (embedding fn is injectable).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from src.models.common import KBPool, stable_id
from src.models.kb import Chunk, ContentOrigin, Source, SourceType
from src.pipeline.kb import _open_collection, chunk_text

log = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _norm_ws(text: str) -> str:
    return " ".join((text or "").split())


def build_query(terms: str, categories: list[str] | None = None) -> str:
    """Build an arXiv ``search_query``. Free-text ``terms`` + an OPTIONAL category filter.

    Categories (e.g. ``["cs.NI", "eess.SP"]``) are supplied by the caller / domain profile —
    never hardwired. With no categories the search is unrestricted (domain-neutral default).
    """
    q = (terms or "").strip()
    search = f"all:{q}" if q else ""
    if categories:
        cat = " OR ".join(f"cat:{c}" for c in categories)
        return f"({search}) AND ({cat})" if search else f"({cat})"
    return search


def parse_arxiv_atom(xml_text: str) -> list[dict]:
    """Parse an arXiv Atom feed into paper dicts. Pure (no I/O).

    Each dict: ``{arxiv_id, title, abstract, authors, year, published, categories, pdf_url,
    abs_url}``.
    """
    root = ET.fromstring(xml_text)
    papers: list[dict] = []
    for entry in root.findall(f"{_ATOM}entry"):
        abs_url = (entry.findtext(f"{_ATOM}id") or "").strip()
        arxiv_id = abs_url.rsplit("/", 1)[-1] if abs_url else ""
        published = (entry.findtext(f"{_ATOM}published") or "").strip()
        year = published[:4] if published[:4].isdigit() else ""
        authors = [_norm_ws(a.findtext(f"{_ATOM}name") or "") for a in entry.findall(f"{_ATOM}author")]
        categories = [c.get("term", "") for c in entry.findall(f"{_ATOM}category") if c.get("term")]
        pdf_url = ""
        for link in entry.findall(f"{_ATOM}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
        papers.append({
            "arxiv_id": arxiv_id,
            "title": _norm_ws(entry.findtext(f"{_ATOM}title") or ""),
            "abstract": _norm_ws(entry.findtext(f"{_ATOM}summary") or ""),
            "authors": [a for a in authors if a],
            "year": year,
            "published": published,
            "categories": categories,
            "pdf_url": pdf_url or abs_url,
            "abs_url": abs_url,
        })
    return papers


def fetch_arxiv(terms: str, categories: list[str] | None = None, max_results: int = 20,
                start: int = 0, sort_by: str = "relevance", timeout: int = 30) -> list[dict]:
    """Query the arXiv Atom API and parse the response. The one network-touching function."""
    params = {
        "search_query": build_query(terms, categories),
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,          # relevance | lastUpdatedDate | submittedDate
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "dilab-foresight/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — fixed arXiv host
        xml_text = resp.read().decode("utf-8")
    return parse_arxiv_atom(xml_text)


def ingest_papers(papers: list[dict], collection=None, collection_name: str = "knowledge_base",
                  persist_dir: str | None = None, pool: KBPool = KBPool.TREND,
                  clear: bool = False, embed_fn=None, state_path: str | None = None,
                  batch: int = 64, max_chunk: int = 1000, min_chunk: int = 80) -> dict:
    """Chunk + embed arXiv abstracts into a Chroma collection using the KB's Source/Chunk shape.

    ``clear`` defaults to False: arXiv ingestion AUGMENTS an existing KB rather than replacing
    it. Metadata mirrors ``kb.ingest`` exactly (``source_id`` + ``year``) so temporal/trends/
    evaluation all work on the added chunks. ``embed_fn`` is injectable for offline tests.
    """
    if collection is None:
        collection = _open_collection(collection_name, persist_dir, clear)
    if embed_fn is None:
        from src.llm import embed as embed_fn  # lazy: keep import light + test-injectable

    sources: dict[str, Source] = {}
    chunks: dict[str, Chunk] = {}
    skipped: list[str] = []
    pend_ids: list[str] = []
    pend_txt: list[str] = []
    pend_meta: list[dict] = []

    # Prefer upsert so re-ingesting the same papers is idempotent (no duplicate-id error);
    # fall back to add for simple/fake collections that only implement add.
    _write = getattr(collection, "upsert", None) or collection.add

    def flush():
        if not pend_txt:
            return
        _write(ids=list(pend_ids), embeddings=embed_fn(pend_txt),
               documents=list(pend_txt), metadatas=list(pend_meta))
        pend_ids.clear(); pend_txt.clear(); pend_meta.clear()

    for p in papers:
        aid = p.get("arxiv_id", "")
        raw = chunk_text(p.get("abstract", "") or "", max_chunk=max_chunk, min_chunk=min_chunk)
        if not raw:  # abstract too short to yield a usable chunk — skip (keeps corpus honest)
            skipped.append(aid or p.get("title", "?"))
            continue

        sid = stable_id("arxiv", aid or p.get("title", ""))
        sources[sid] = Source(id=sid, title=p.get("title", aid) or aid,
                              url=p.get("pdf_url", "") or p.get("abs_url", ""),
                              type=SourceType.RESEARCH_PAPER, pool=pool,
                              content_origin=ContentOrigin.FETCHED)
        for text in raw:
            cid = stable_id(sid, text[:200])
            chunks[cid] = Chunk(id=cid, source_id=sid, content=text, section="arxiv", pool=pool)
            pend_ids.append(cid)
            pend_txt.append(text)
            pend_meta.append({
                "source_id": sid, "source_title": sources[sid].title, "pool": pool.value,
                "section": "arxiv", "publisher": "arXiv", "year": str(p.get("year", "")),
            })
            if len(pend_ids) >= batch:
                flush()
    flush()

    if state_path:
        state = {"sources": {k: v.model_dump(mode="json") for k, v in sources.items()},
                 "chunks": {k: v.model_dump(mode="json") for k, v in chunks.items()}}
        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    return {"collection": collection, "sources": sources, "chunks": chunks,
            "n_chunks": len(chunks), "skipped": skipped}


def run(query: str, categories: list[str] | None = None, max_results: int = 50,
        collection_name: str = "knowledge_base", persist_dir: str | None = None,
        pool: KBPool = KBPool.TREND, clear: bool = False,
        output_path: str = "data/outputs/arxiv_kb_state.json") -> dict:
    """Fetch papers for a (domain-derived) query and augment the KB. Returns ingest summary."""
    papers = fetch_arxiv(query, categories=categories, max_results=max_results)
    res = ingest_papers(papers, collection_name=collection_name, persist_dir=persist_dir,
                        pool=pool, clear=clear, state_path=output_path)
    log.info("arXiv ingest: %d papers → %d chunks (%d skipped)",
             len(papers), res["n_chunks"], len(res["skipped"]))
    return {"n_papers": len(papers), "n_chunks": res["n_chunks"],
            "skipped": res["skipped"], "sources": len(res["sources"])}
