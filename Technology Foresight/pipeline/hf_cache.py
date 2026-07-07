"""Use a project-local Hugging Face cache (avoids ~/.cache permission errors)."""
from __future__ import annotations

import os
from pathlib import Path

_CONFIGURED = False
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HF_ROOT = PROJECT_ROOT / ".cache" / "huggingface"


def configure_hf_cache() -> Path:
    """Point Hugging Face / sentence-transformers caches inside the project directory."""
    global _CONFIGURED
    if _CONFIGURED:
        return HF_ROOT

    HF_ROOT.mkdir(parents=True, exist_ok=True)
    hub = HF_ROOT / "hub"
    hub.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(HF_ROOT)
    os.environ["HF_HUB_CACHE"] = str(hub)
    os.environ["TRANSFORMERS_CACHE"] = str(HF_ROOT / "transformers")
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(HF_ROOT / "sentence_transformers")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    # Avoid writing lock files into a protected user cache
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    _CONFIGURED = True
    return HF_ROOT


def sentence_transformers_cache_dir() -> str:
    return str(configure_hf_cache() / "sentence_transformers")
