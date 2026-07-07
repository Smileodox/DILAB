from __future__ import annotations

import chromadb

from src.config import CHROMA_PERSIST_DIR, MAX_RAG_CHUNKS
from src.llm import embed


def get_collection(name: str = "knowledge_base") -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return client.get_collection(name)


def retrieve(
    collection: chromadb.Collection,
    query: str,
    pool: str | None = None,
    n: int = MAX_RAG_CHUNKS,
) -> list[dict]:
    query_emb = embed([query])[0]
    kwargs: dict = {
        "query_embeddings": [query_emb],
        "n_results": n,
        "include": ["documents", "metadatas"],
    }
    if pool is not None:
        kwargs["where"] = {"pool": pool}
    results = collection.query(**kwargs)
    out = []
    for i in range(len(results["ids"][0])):
        out.append({
            "chunk_id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "source_title": results["metadatas"][0][i]["source_title"],
        })
    return out


def format_rag_chunks(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f"[Chunk ID: {c['chunk_id']}] (Source: {c['source_title']})\n{c['content']}"
        )
    return "\n\n---\n\n".join(parts)
