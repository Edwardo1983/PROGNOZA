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


def normalize_openweather(payload: Dict[str, Any], *, mode: str = "onecall") -> pd.DataFrame:
    """Normalize OpenWeather responses for both One Call and forecast APIs."""
    if mode == "forecast":
        return normalize_openweather_forecast(payload)
    return normalize_openweather_onecall(payload)


def normalize_openweather_onecall(payload: Dict[str, Any]) -> pd.DataFrame:
    # Validate payload structure
    if not payload or not isinstance(payload, dict):
        return _build_frame([])

    rows: List[Dict[str, Any]] = []

    def _extract(entry: Dict[str, Any]) -> None:
        if not entry:
            return
        timestamp = entry.get("dt")
        if timestamp is None:
            return
        try:
            dt = pd.Timestamp.fromtimestamp(timestamp, tz="UTC")
        except (ValueError, OSError, OverflowError):
            return
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
    hourly_data = payload.get("hourly")
    if hourly_data and isinstance(hourly_data, list):
        for entry in hourly_data:
            _extract(entry)

    frame = _build_frame(rows)
    if not frame.empty:
        frame["temp_C"] = frame["temp_C"].apply(lambda v: float(v) if v is not None else np.nan)
        frame["wind_ms"] = frame["wind_ms"].apply(lambda v: float(v) if v is not None else np.nan)
    return frame


def normalize_openweather_forecast(payload: Dict[str, Any]) -> pd.DataFrame:
    """Normalize OpenWeather free-plan forecast (3-hour) and current weather data."""
    if not payload or not isinstance(payload, dict):
        return _build_frame([])

    forecast = payload.get("forecast") or {}
    current = payload.get("current") or {}
    rows: List[Dict[str, Any]] = []

    def _append_entry(dt_seconds: int, data: Dict[str, Any], *, main_key: str = "main") -> None:
        try:
            dt = pd.Timestamp.fromtimestamp(dt_seconds, tz="UTC")
        except (ValueError, OSError, OverflowError):
            return
        main_block = data.get(main_key, data)
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        rows.append(
            {
                "timestamp": dt,
                "temp_C": _safe_float(main_block.get("temp")),
                "wind_ms": _safe_float(wind.get("speed")),
                "wind_deg": _safe_float(wind.get("deg")),
                "clouds_pct": _safe_float(clouds.get("all")),
                "humidity": _safe_float(main_block.get("humidity")),
                "uvi": np.nan,
                "ghi_Wm2": np.nan,
            }
        )

    if isinstance(current, dict) and "dt" in current:
        _append_entry(int(current["dt"]), current)

    forecast_list = forecast.get("list")
    if isinstance(forecast_list, list):
        for item in forecast_list:
            if not isinstance(item, dict):
                continue
            dt_val = item.get("dt")
            if dt_val is None:
                continue
            _append_entry(int(dt_val), item)

    frame = _build_frame(rows)
    # Remove duplicate timestamps keeping latest (forecast overrides current)
    if not frame.empty:
        frame = frame[~frame.index.duplicated(keep="last")]
    return frame


def normalize_openmeteo(payload: Dict[str, Any]) -> pd.DataFrame:
    # Validate payload structure
    if not payload or not isinstance(payload, dict):
        return _build_frame([])

    hourly = payload.get("hourly")
    if not hourly or not isinstance(hourly, dict):
        return _build_frame([])

    timestamps = hourly.get("time")
    if not timestamps or not isinstance(timestamps, (list, tuple)):
        return _build_frame([])

    rows = []
    hourly_units = payload.get("hourly_units", {})
    wind_units = hourly_units.get("windspeed_10m") if isinstance(hourly_units, dict) else None

    for idx, ts in enumerate(timestamps):
        try:
            dt = pd.to_datetime(ts, utc=True)
        except (ValueError, TypeError):
            # Skip invalid timestamps
            continue
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
    """Get value from mapping with fallback to model-suffixed keys."""
    # Try exact key first
    values = mapping.get(key)
    if values:
        try:
            value = values[index]
            if value is not None:
                return float(value)
        except (IndexError, TypeError, ValueError):
            pass

    # If not found or value is None, try keys with model suffixes
    # (e.g., temperature_2m_ecmwf_ifs04, temperature_2m_icon_seamless)
    for map_key in sorted(mapping.keys()):  # Sort for deterministic order
        if map_key.startswith(key + "_"):
            candidate_values = mapping.get(map_key)
            if candidate_values:
                try:
                    candidate_value = candidate_values[index]
                    if candidate_value is not None:
                        return float(candidate_value)
                except (IndexError, TypeError, ValueError):
                    continue  # Try next model

    return None


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
    # Validate payload structure
    if not payload or not isinstance(payload, dict):
        return _build_frame([])

    data = payload.get("data")
    if not data or not isinstance(data, dict):
        return _build_frame([])

    timelines = data.get("timelines")
    if not timelines or not isinstance(timelines, list):
        return _build_frame([])

    rows: List[Dict[str, Any]] = []
    for timeline in timelines:
        if not isinstance(timeline, dict):
            continue
        intervals = timeline.get("intervals")
        if not intervals or not isinstance(intervals, list):
            continue
        for interval in intervals:
            if not isinstance(interval, dict):
                continue
            timestamp = interval.get("startTime")
            if timestamp is None:
                continue
            try:
                dt = pd.to_datetime(timestamp, utc=True)
            except (ValueError, TypeError):
                # Skip invalid timestamps
                continue
            values = interval.get("values")
            if not isinstance(values, dict):
                values = {}
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
