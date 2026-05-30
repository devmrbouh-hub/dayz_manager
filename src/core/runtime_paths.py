"""Runtime-aware paths for writable app data."""

from __future__ import annotations

import sys
from pathlib import Path


def get_runtime_base_dir() -> Path:
    """Return the writable install root used by config/data files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_runtime_data_file(name: str) -> Path:
    """Return a file path under the external data directory."""
    return get_runtime_base_dir() / "data" / name
