"""Typer-based CLI entry package for PROGONZA."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = Path(__file__).resolve().parent / "locales"
RC_FILE = APP_ROOT / ".progonzarc"

__all__ = ["APP_ROOT", "LOCALES_DIR", "RC_FILE"]
