"""Resolve project paths so this package can import the shared backend services."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
MODULE_ROOT = PACKAGE_DIR.parent
PROJECT_ROOT = MODULE_ROOT.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def ensure_backend_on_path() -> Path:
    backend = str(BACKEND_DIR)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    return BACKEND_DIR
