"""Run NB01 knowledge base ingestion as a standalone script."""
from __future__ import annotations

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import fitz
import chromadb

from src.config import CHROMA_PERSIST_DIR
from src.llm import embed
from src.models.kb import Source, Chunk, SourceType, ContentOrigin
from src.models.common import KBPool, stable_id

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "pdfs")
SOURCES_GENERAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "sources.json")
SOURCES_RS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "sources_rs.json")

CATEGORY_POOL = {
    "A_regulator_canonical":    KBPool.TREND,
    "B_regional_regulator":     KBPool.TREND,
    "C_us_regulator":           KBPool.TREND,
    "D_eu_strategy":            KBPool.TREND,
    "E_industry_international": KBPool.TREND,
    "F_academic_ai_ml":         KBPool.TREND,
    "G_academic_sensing":       KBPool.TREND,
    "H_security":               KBPool.TREND,
    "I_measurement_framework":  KBPool.TREND,
    "J_system_overview":        KBPool.PRODUCT,
    "K_receivers":              KBPool.PRODUCT,
    "L_direction_finders":      KBPool.PRODUCT,
    "M_antennas":               KBPool.PRODUCT,
    "N_software_systems":       KBPool.PRODUCT,
    "P_application_notes":      KBPool.PRODUCT,
}

CATEGORY_TYPE = {
    "A_regulator_canonical":    SourceType.REGULATION,
    "B_regional_regulator":     SourceType.REGULATION,
    "C_us_regulator":           SourceType.REGULATION,
    "D_eu_strategy":            SourceType.REGULATION,
    "E_industry_international": SourceType.TREND_REPORT,
    "F_academic_ai_ml":         SourceType.RESEARCH_PAPER,
    "G_academic_sensing":       SourceType.RESEARCH_PAPER,
    "H_security":               SourceType.TECH_ARTICLE,
    "I_measurement_framework":  SourceType.REGULATION,
    "J_system_overview":        SourceType.TECH_ARTICLE,
    "K_receivers":              SourceType.PRODUCT_PAGE,
    "L_direction_finders":      SourceType.PRODUCT_PAGE,
    "M_antennas":               SourceType.PRODUCT_PAGE,
    "N_software_systems":       SourceType.PRODUCT_PAGE,
    "P_application_notes":      SourceType.DATASHEET,
}


def extract_chunks(pdf_path: str, max_chunk: int = 1000, min_chunk: int = 80) -> list[str]:
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    doc.close()
    full_text = "\n\n".join(pages_text)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = re.sub(r"[ \t]+", " ", full_text)
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    chunks, buf = [], ""
    for para in paragraphs:
        if len(para) < 25:
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


def load_entries(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data["sources"]


def main() -> None:
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        client.delete_collection("knowledge_base")
        print("Cleared existing collection")
    except Exception:
        print("No existing collection")
    collection = client.get_or_create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )

    entries = load_entries(SOURCES_GENERAL) + load_entries(SOURCES_RS)
    print(f"Entries: {len(entries)}")

    sources: dict[str, Source] = {}
    chunks: dict[str, Chunk] = {}
    skipped: list[str] = []

    BATCH = 64
    pending_ids: list[str] = []
    pending_texts: list[str] = []
    pending_metas: list[dict] = []

    def flush() -> None:
        if not pending_texts:
            return
        t0 = time.time()
        embeddings = embed(pending_texts)
        collection.add(ids=pending_ids, embeddings=embeddings, documents=pending_texts, metadatas=pending_metas)
        print(f"    embedded {len(pending_texts)} chunks in {time.time()-t0:.1f}s")
        pending_ids.clear(); pending_texts.clear(); pending_metas.clear()

    t_start = time.time()
    for entry in entries:
        filename = entry.get("filename", "")
        pdf_path = os.path.join(PDF_DIR, filename)
        if not filename or not os.path.exists(pdf_path):
            skipped.append(entry["id"])
            print(f"  [SKIP] {entry['id']}")
            continue

        category = entry.get("category", "")
        pool = CATEGORY_POOL.get(category, KBPool.TREND)
        stype = CATEGORY_TYPE.get(category, SourceType.TECH_ARTICLE)
        source_id = entry["id"]

        src = Source(
            id=source_id,
            title=entry["title"],
            url=entry.get("url", ""),
            type=stype,
            pool=pool,
            content_origin=ContentOrigin.FETCHED,
        )
        sources[source_id] = src

        t0 = time.time()
        raw_chunks = extract_chunks(pdf_path)
        print(f"  [OK ] {source_id:55s} {len(raw_chunks):4d} chunks  (extract {time.time()-t0:.1f}s)")

        for text in raw_chunks:
            chunk_id = stable_id(source_id, text[:200])
            chunks[chunk_id] = Chunk(id=chunk_id, source_id=source_id, content=text, section=category, pool=pool)
            pending_ids.append(chunk_id)
            pending_texts.append(text)
            pending_metas.append({
                "source_id": source_id,
                "source_title": src.title,
                "pool": pool.value,
                "section": category,
                "publisher": entry.get("publisher", ""),
                "year": str(entry.get("year", "")),
            })
            if len(pending_ids) >= BATCH:
                flush()

    flush()

    print(f"\n{'='*60}")
    print(f"Sources processed : {len(sources)}")
    print(f"Sources skipped   : {len(skipped)} — {skipped}")
    print(f"Total chunks      : {len(chunks)}")
    print(f"ChromaDB docs     : {collection.count()}")
    print(f"Total time        : {time.time()-t_start:.0f}s")

    os.makedirs("data/outputs", exist_ok=True)
    state = {
        "sources": {k: v.model_dump(mode="json") for k, v in sources.items()},
        "chunks": {k: v.model_dump(mode="json") for k, v in chunks.items()},
    }
    with open("data/outputs/kb_state.json", "w") as f:
        json.dump(state, f, indent=2, default=str)
    print("Saved data/outputs/kb_state.json")


if __name__ == "__main__":
    main()
