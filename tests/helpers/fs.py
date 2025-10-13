"""Filesystem helpers for the pytest suite."""

from __future__ import annotations

from pathlib import Path

__all__ = ["ensure_directory"]


def ensure_directory(path: Path) -> Path:
    """Create parent directories for ``path`` and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
