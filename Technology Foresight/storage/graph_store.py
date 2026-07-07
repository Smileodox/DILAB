"""Persist and load pipeline results per job."""
import json
import os
from pathlib import Path
from typing import Any

UPLOADS_ROOT = Path(__file__).resolve().parent.parent / "uploads"


def job_dir(job_id: str) -> Path:
    d = UPLOADS_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_result(job_id: str, data: dict[str, Any]) -> Path:
    path = job_dir(job_id) / "result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def load_result(job_id: str) -> dict[str, Any] | None:
    path = job_dir(job_id) / "result.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_progress(job_id: str, stage: str, percent: int, label: str) -> None:
    path = job_dir(job_id) / "progress.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"stage": stage, "percent": percent, "label": label}, f)


def load_progress(job_id: str) -> dict[str, Any]:
    path = job_dir(job_id) / "progress.json"
    if not path.exists():
        return {"stage": "pending", "percent": 0, "label": "Waiting…"}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_corpus(job_id: str, documents: list[dict]) -> None:
    path = job_dir(job_id) / "corpus.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, default=str)


def load_corpus(job_id: str) -> list[dict]:
    path = job_dir(job_id) / "corpus.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_job_meta(job_id: str, meta: dict[str, Any]) -> None:
    path = job_dir(job_id) / "job_meta.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)


def load_job_meta(job_id: str) -> dict[str, Any]:
    path = job_dir(job_id) / "job_meta.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
