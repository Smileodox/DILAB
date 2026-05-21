from __future__ import annotations
import hashlib
import uuid
from enum import Enum

__all__ = ["_id", "stable_id", "KBPool"]


def _id() -> str:
    return uuid.uuid4().hex[:12]


def stable_id(*parts: str) -> str:
    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


class KBPool(str, Enum):
    PRODUCT = "product"
    TREND = "trend"
