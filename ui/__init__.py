"""UI package for the PROGONZA dashboard."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"

__all__ = ["APP_ROOT", "DATA_DIR"]
