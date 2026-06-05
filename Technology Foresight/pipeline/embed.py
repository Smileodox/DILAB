"""Embed document texts with sentence-transformers."""
from __future__ import annotations

import numpy as np

from pipeline.hf_cache import configure_hf_cache, sentence_transformers_cache_dir

configure_hf_cache()

_MODEL = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(
            _MODEL_NAME,
            cache_folder=sentence_transformers_cache_dir(),
        )
    return _MODEL


def embed_texts(texts: list[str]) -> np.ndarray:
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(embeddings, dtype=np.float32)
