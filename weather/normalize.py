"""Normalization helpers for provider data."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .core import REQUIRED_COLUMNS, ensure_schema


def _build_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            index=pd.DatetimeIndex([], tz="UTC"),
            columns=REQUIRED_COLUMNS,
            dtype=float,
        )
    frame = pd.DataFrame(rows)
    if "timestamp" not in frame.columns:
        raise ValueError("Normalized rows must include 'timestamp'")
    frame = frame.set_index("timestamp")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame = frame.sort_index()
    return ensure_schema(frame)


def kelvin_to_celsius(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) - 273.15


def kmh_to_ms(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return float(value) / 3.6


def normalize_openweather(payload: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    def _extract(entry: Dict[str, Any]) -> None:
        if not entry:
            return
        timestamp = entry.get("dt")
        if timestamp is None:
            return
        dt = pd.Timestamp.utcfromtimestamp(timestamp)
        rows.append(
            {
                "timestamp": dt,
                "temp_C": entry.get("temp"),
                "wind_ms": entry.get("wind_speed"),
                "wind_deg": entry.get("wind_deg"),
                "clouds_pct": entry.get("clouds"),
                "humidity": entry.get("humidity"),
                "uvi": entry.get("uvi"),
                "ghi_Wm2": np.nan,
            }
        )

    current = payload.get("current")
    if current:
        _extract(current)
    for entry in payload.get("hourly", []):
        _extract(entry)

    frame = _build_frame(rows)
    if not frame.empty:
        frame["temp_C"] = frame["temp_C"].apply(lambda v: float(v) if v is not None else np.nan)
        frame["wind_ms"] = frame["wind_ms"].apply(lambda v: float(v) if v is not None else np.nan)
    return frame


def normalize_openmeteo(payload: Dict[str, Any]) -> pd.DataFrame:
    hourly = payload.get("hourly") or {}
    timestamps = hourly.get("time") or []
    if not timestamps:
        return _build_frame([])
    rows = []
    hourly_units = payload.get("hourly_units", {})
    wind_units = hourly_units.get("windspeed_10m")
    for idx, ts in enumerate(timestamps):
        dt = pd.to_datetime(ts, utc=True)
        rows.append(
            {
                "timestamp": dt,
                "temp_C": _at(hourly, "temperature_2m", idx),
                "wind_ms": _convert_windspeed(hourly, wind_units, idx),
                "wind_deg": _at(hourly, "winddirection_10m", idx),
                "clouds_pct": _at(hourly, "cloudcover", idx),
                "humidity": _at(hourly, "relativehumidity_2m", idx),
                "uvi": _at(hourly, "uv_index", idx),
                "ghi_Wm2": _at(hourly, "shortwave_radiation", idx),
            }
        )
    frame = _build_frame(rows)
    return frame


def _at(mapping: Dict[str, Iterable[Any]], key: str, index: int) -> Optional[float]:
    values = mapping.get(key)
    if not values:
        return None
    try:
        value = values[index]
    except IndexError:
        return None
    return None if value is None else float(value)


def _convert_windspeed(hourly: Dict[str, Iterable[Any]], units: Optional[str], idx: int) -> Optional[float]:
    value = _at(hourly, "windspeed_10m", idx)
    if value is None:
        return None
    if not units:
        # fall back to API metadata if available
        return float(value)
    units = str(units).lower()
    if "km/h" in units or "kph" in units:
        return kmh_to_ms(value)
    return float(value)


def normalize_tomorrow(payload: Dict[str, Any]) -> pd.DataFrame:
    timelines = payload.get("data", {}).get("timelines") or []
    if not timelines:
        return _build_frame([])

    rows: List[Dict[str, Any]] = []
    for timeline in timelines:
        intervals = timeline.get("intervals") or []
        for interval in intervals:
            timestamp = interval.get("startTime")
            values = interval.get("values") or {}
            if timestamp is None:
                continue
            dt = pd.to_datetime(timestamp, utc=True)
            rows.append(
                {
                    "timestamp": dt,
                    "temp_C": _safe_float(values.get("temperature")),
                    "wind_ms": _safe_float(values.get("windSpeed")),
                    "wind_deg": _safe_float(values.get("windDirection")),
                    "clouds_pct": _safe_float(values.get("cloudCover")),
                    "humidity": _safe_float(values.get("humidity")),
                    "uvi": _safe_float(values.get("uvIndex")),
                    "ghi_Wm2": _safe_float(values.get("solarGHI")),
                }
            )
    return _build_frame(rows)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def empty_frame() -> pd.DataFrame:
    return _build_frame([])
