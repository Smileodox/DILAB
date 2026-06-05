"""Cluster embeddings with BERTopic and produce UMAP coordinates."""
from __future__ import annotations

import re
from typing import Any

import numpy as np
from bertopic import BERTopic
from bertopic.representation import MaximalMarginalRelevance
from bertopic.vectorizers import ClassTfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

from pipeline.hf_cache import configure_hf_cache, sentence_transformers_cache_dir
from pipeline.stopwords import filter_keyword_list, get_vectorizer_stop_words

configure_hf_cache()


def _preprocess_for_vectorizer(text: str) -> str:
    """Light normalization so c-TF-IDF focuses on content words."""
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\barxiv:\d+\.\d+v?\d*\b", " ", text)
    text = re.sub(r"\b\d{4}\b", " ", text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_vectorizer(n_docs: int) -> CountVectorizer:
    min_df = 1 if n_docs < 12 else max(2, int(n_docs * 0.05))
    max_df = 0.85 if n_docs >= 15 else 0.95
    return CountVectorizer(
        stop_words=get_vectorizer_stop_words(),
        ngram_range=(1, 2),
        min_df=min_df,
        max_df=max_df,
        max_features=8000,
        preprocessor=_preprocess_for_vectorizer,
        token_pattern=r"(?u)\b[a-z][a-z0-9\-]{2,}\b",
    )


def _extract_topic_keywords(topic_model: BERTopic, topic_id: int) -> list[str]:
    raw = topic_model.get_topic(topic_id) or []
    filtered = filter_keyword_list(raw, limit=15)
    if filtered:
        return filtered[:12]
    # Fallback: take longest non-stop unigrams from raw list
    fallback = []
    for word, _ in raw:
        w = word.strip().lower()
        if len(w) >= 4 and w not in get_vectorizer_stop_words():
            fallback.append(w)
        if len(fallback) >= 8:
            break
    return fallback or [f"topic_{topic_id}"]


def run_clustering(texts: list[str], embeddings: np.ndarray) -> dict[str, Any]:
    n_docs = len(texts)
    min_topic_size = max(2, min(5, n_docs // 8))

    umap_model = UMAP(
        n_neighbors=min(15, max(2, n_docs - 1)),
        n_components=2,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )

    vectorizer_model = _build_vectorizer(n_docs)
    ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True)
    representation_model = MaximalMarginalRelevance(diversity=0.35)

    try:
        from sentence_transformers import SentenceTransformer

        embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            cache_folder=sentence_transformers_cache_dir(),
        )
    except Exception:
        embedding_model = None

    topic_model = BERTopic(
        umap_model=umap_model,
        vectorizer_model=vectorizer_model,
        ctfidf_model=ctfidf_model,
        representation_model=representation_model,
        embedding_model=embedding_model,
        min_topic_size=min_topic_size,
        top_n_words=15,
        verbose=False,
        calculate_probabilities=False,
    )
    topics, _ = topic_model.fit_transform(texts, embeddings)
    topic_info = topic_model.get_topic_info()
    reduced = getattr(topic_model.umap_model, "embedding_", None)
    if reduced is None:
        reduced = umap_model.fit_transform(embeddings)

    clusters = []
    for _, row in topic_info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue
        keywords = _extract_topic_keywords(topic_model, tid)
        clusters.append(
            {
                "topic_id": tid,
                "count": int(row["Count"]),
                "keywords": keywords,
                "label": ", ".join(keywords[:4]) if keywords else f"Topic {tid}",
            }
        )

    if not clusters:
        clusters = [{"topic_id": 0, "count": n_docs, "keywords": ["general"], "label": "general"}]
        topics = [0] * n_docs
        reduced = np.random.default_rng(42).normal(size=(n_docs, 2)) * 0.1

    points = []
    for i, text in enumerate(texts):
        tid = int(topics[i]) if topics[i] != -1 else int(clusters[0]["topic_id"])
        points.append(
            {
                "doc_index": i,
                "topic_id": tid,
                "x": float(reduced[i, 0]),
                "y": float(reduced[i, 1]),
                "preview": text[:120].replace("\n", " "),
            }
        )

    return {
        "topics": [int(t) if t != -1 else int(clusters[0]["topic_id"]) for t in topics],
        "clusters": clusters,
        "points": points,
        "why": (
            "Documents were embedded with all-MiniLM-L6-v2, projected with UMAP, and grouped by "
            "BERTopic (HDBSCAN + c-TF-IDF). Topic labels use an English + academic stop-word list, "
            "bigrams, reduced-frequent-word c-TF-IDF, and Maximal Marginal Relevance so keywords "
            "highlight technology terms—not function words like “the” or “of”."
        ),
    }
