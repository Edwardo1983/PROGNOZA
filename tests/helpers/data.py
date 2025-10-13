"""Synthetic data builders used across the pytest suite."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

__all__ = [
    "build_fake_umg_frame",
    "build_fake_weather_frame",
    "write_csv",
    "write_parquet",
]


def build_fake_umg_frame(
    *,
    start: str | datetime = "2024-01-01T00:00:00Z",
    periods: int = 60,
    freq: str = "1min",
) -> pd.DataFrame:
    """Return a Janitza-like measurement dataframe with deterministic values."""
    index = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")
    base = np.linspace(0, 2 * np.pi, periods, endpoint=False)
    utc_index = index.tz_convert("UTC")
    frame = pd.DataFrame(
        {
            "timestamp": utc_index.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "power_active_total": 50 + 10 * np.sin(base),
            "power_reactive_total": 5 + 2 * np.cos(base),
            "power_apparent_total": 60 + 8 * np.sin(base / 2),
            "voltage_l1": 230 + 5 * np.sin(base / 3),
            "current_l1": 10 + np.cos(base),
            "frequency": 50 + 0.02 * np.sin(base * 3),
            "power_factor": 0.95 + 0.02 * np.cos(base * 2),
            "thd_voltage_l1": 1.5 + 0.1 * np.sin(base * 1.5),
            "thd_current_l1": 2.5 + 0.1 * np.cos(base * 1.5),
        }
    )
    frame["power_W"] = frame["power_active_total"] * 1000 / 3.6  # convert to W-ish
    return frame


def build_fake_weather_frame(
    *,
    start: str | datetime = "2024-01-01T00:00:00Z",
    periods: int = 72,
    freq: str = "1h",
) -> pd.DataFrame:
    """Return a deterministic hourly weather dataframe."""
    index = pd.date_range(start=start, periods=periods, freq=freq, tz="UTC")
    hours = np.arange(periods)
    frame = pd.DataFrame(
        {
            "temp_C": 5 + 10 * np.sin(hours / 24 * 2 * np.pi),
            "wind_ms": 3 + np.cos(hours / 12 * 2 * np.pi),
            "wind_deg": (hours * 15) % 360,
            "clouds_pct": np.clip(50 + 30 * np.sin(hours / 6), 0, 100),
            "humidity": np.clip(60 + 10 * np.cos(hours / 5), 0, 100),
            "uvi": np.clip(2 + np.sin(hours / 24 * 2 * np.pi), 0, None),
            "ghi_Wm2": np.clip(100 + 50 * np.sin(hours / 24 * 2 * np.pi), 0, None),
        },
        index=index,
    )
    return frame


def write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_parquet(path)
    except ImportError:  # pragma: no cover - optional dependency fallback
        fallback = path.with_suffix(".csv")
        frame.to_csv(fallback)
        return fallback
    return path
