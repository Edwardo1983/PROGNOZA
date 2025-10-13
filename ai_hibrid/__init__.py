"""Hybrid forecasting package."""
from __future__ import annotations

import importlib
from typing import Any

__all__ = ["pipeline", "features", "models", "metrics"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
