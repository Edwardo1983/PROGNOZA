"""Unified weather ingestion package with pluggable providers."""
from __future__ import annotations

from typing import Any

from .core import ForecastFrame, Provider, REQUIRED_COLUMNS, ensure_utc_index, to_local

__all__ = [
    "ForecastFrame",
    "Provider",
    "REQUIRED_COLUMNS",
    "ensure_utc_index",
    "to_local",
    "WeatherRouter",
    "load_weather_config",
]


def __getattr__(name: str) -> Any:
    if name in {"WeatherRouter", "load_weather_config"}:
        from .router import WeatherRouter, load_weather_config

        return {"WeatherRouter": WeatherRouter, "load_weather_config": load_weather_config}[name]
    raise AttributeError(f"module 'weather' has no attribute '{name}'")
