"""Knowledge Base ingest step — the docking point of the domain-agnostic pipeline.

Chunk a corpus of PDFs and embed them into a persistent ChromaDB collection. Reusable
across domains: point it at a different PDF folder + collection name and every downstream
step derives the rest from the resulting KB (see src.pipeline.domain). The module itself
is domain-neutral — no domain taxonomy is hardwired here.

Extracted from notebooks/01_knowledge_base.ipynb so the ingest is importable and testable
(the notebook was previously the only home of this logic).
"""
from __future__ import annotations

import json
import logging
import os
import re

import chromadb

from src.config import CHROMA_PERSIST_DIR
from src.llm import embed
from src.models.common import KBPool, stable_id
from src.models.kb import Chunk, ContentOrigin, Source, SourceType

log = logging.getLogger(__name__)


def chunk_text(full_text: str, max_chunk: int = 1000, min_chunk: int = 80) -> list[str]:
    """Paragraph-pack a document's text into ~max_chunk-sized chunks. Pure (no I/O)."""
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = re.sub(r"[ \t]+", " ", full_text)
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]

    chunks, buf = [], ""
    for para in paragraphs:
        if len(para) < 25:  # skip page numbers, lone headers
            continue
        if len(buf) + len(para) + 2 <= max_chunk:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if len(buf) >= min_chunk:
                chunks.append(buf)
            buf = para
    if len(buf) >= min_chunk:
        chunks.append(buf)
    return chunks


def extract_chunks(pdf_path: str, max_chunk: int = 1000, min_chunk: int = 80) -> list[str]:
    """Extract text from a PDF (pymupdf) and paragraph-chunk it. Mirrors notebook 01."""
    import fitz  # pymupdf — imported lazily so chunk_text stays dependency-free

    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    doc.close()
    return chunk_text("\n\n".join(pages_text), max_chunk=max_chunk, min_chunk=min_chunk)


def _open_collection(name: str, persist_dir: str | None, clear: bool):
    client = chromadb.PersistentClient(path=persist_dir or CHROMA_PERSIST_DIR)
    if clear:
        try:
            client.delete_collection(name)
        except Exception:  # noqa: BLE001 — collection may not exist yet
            pass
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def ingest(entries: list[dict], pdf_dir: str, collection_name: str = "knowledge_base",
           persist_dir: str | None = None, default_pool: KBPool = KBPool.TREND,
           default_type: SourceType = SourceType.RESEARCH_PAPER, batch: int = 64,
           clear: bool = True, state_path: str | None = None) -> dict:
    """Chunk + embed a list of PDF source entries into a persistent Chroma collection.

    entries: dicts with at least {"id", "title", "filename"}; optional keys
             {"url", "publisher", "year", "category", "pool"}. Missing PDFs are skipped.
    Returns {"collection", "sources", "chunks", "n_chunks", "skipped"}.
    """
    collection = _open_collection(collection_name, persist_dir, clear)
    sources: dict[str, Source] = {}
    chunks: dict[str, Chunk] = {}
    skipped: list[str] = []
    pend_ids: list[str] = []
    pend_txt: list[str] = []
    pend_meta: list[dict] = []

    def flush():
        if not pend_txt:
            return
        collection.add(ids=list(pend_ids), embeddings=embed(pend_txt),
                       documents=list(pend_txt), metadatas=list(pend_meta))
        pend_ids.clear(); pend_txt.clear(); pend_meta.clear()

    for e in entries:
        filename = e.get("filename", "")
        path = os.path.join(pdf_dir, filename)
        if not filename or not os.path.exists(path):
            skipped.append(e.get("id", filename))
            log.warning("  [SKIP] %s — PDF not found", e.get("id", filename))
            continue

        pool = KBPool(e["pool"]) if e.get("pool") else default_pool
        sid = e.get("id") or stable_id(filename)
        sources[sid] = Source(id=sid, title=e.get("title", filename), url=e.get("url", ""),
                              type=default_type, pool=pool, content_origin=ContentOrigin.FETCHED)

        raw = extract_chunks(path)
        for text in raw:
            cid = stable_id(sid, text[:200])
            chunks[cid] = Chunk(id=cid, source_id=sid, content=text,
                                section=e.get("category", ""), pool=pool)
            pend_ids.append(cid)
            pend_txt.append(text)
            pend_meta.append({
                "source_id": sid, "source_title": sources[sid].title, "pool": pool.value,
                "section": e.get("category", ""), "publisher": e.get("publisher", ""),
                "year": str(e.get("year", "")),
            })
            if len(pend_ids) >= batch:
                flush()
        log.info("  [OK] %-50s %4d chunks", sid, len(raw))
    flush()

    if state_path:
        state = {"sources": {k: v.model_dump(mode="json") for k, v in sources.items()},
                 "chunks": {k: v.model_dump(mode="json") for k, v in chunks.items()}}
        os.makedirs(os.path.dirname(os.path.abspath(state_path)), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    return {"collection": collection, "sources": sources, "chunks": chunks,
            "n_chunks": len(chunks), "skipped": skipped}


def run(output_path: str = "data/outputs/kb_state.json",
        sources_files: list[str] | None = None, pdf_dir: str = "knowledge_base/pdfs",
        collection_name: str = "knowledge_base", persist_dir: str | None = None,
        category_pool: dict | None = None, category_type: dict | None = None,
        clear: bool = True) -> dict:
    """Registry-based ingest for the primary KB (replaces notebook 01's manual loop).

    Reads source registries (each a JSON ``{"sources": [...]}``), optionally maps each
    entry's ``category`` to a pool/type, and ingests every referenced PDF.
    """
    sources_files = sources_files or ["knowledge_base/sources.json", "knowledge_base/sources_rs.json"]
    entries: list[dict] = []
    for sf in sources_files:
        if os.path.exists(sf):
            with open(sf) as f:
                entries.extend(json.load(f).get("sources", []))

    for e in entries:  # resolve per-entry pool from a caller-supplied category map
        cat = e.get("category", "")
        if category_pool and cat in category_pool and not e.get("pool"):
            e["pool"] = category_pool[cat].value if isinstance(category_pool[cat], KBPool) else category_pool[cat]

    res = ingest(entries, pdf_dir, collection_name=collection_name, persist_dir=persist_dir,
                 clear=clear, state_path=output_path)
    return {k: v for k, v in res.items() if k != "collection"}
