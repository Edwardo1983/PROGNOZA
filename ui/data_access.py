"""Data access helpers for the PROGONZA UI."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from dateutil import tz

from . import APP_ROOT
from .schemas import MetricRow, SeriesPayload, SeriesPoint, SeriesResponse

LOGGER = logging.getLogger(__name__)

JANITZA_DIRS = [
    APP_ROOT / "data" / "raw" / "umg509",
    APP_ROOT / "data" / "exports",
]
WEATHER_DIR = APP_ROOT / "data" / "weather"
FORECASTS_DIR = APP_ROOT / "data" / "forecasts"
RESAMPLE_RULE = "5min"

UTC = tz.gettz("UTC")

PALETTE = [
    "#0062ff",
    "#8a3ffc",
    "#ff832b",
    "#24a148",
    "#d12771",
    "#009d9a",
    "#a56eff",
    "#ff7eb6",
    "#fa4d56",
    "#0f62fe",
    "#42be65",
    "#be95ff",
    "#7d8de7",
    "#12c2e9",
    "#c471ed",
    "#f64f59",
    "#ee5396",
    "#f1c21b",
    "#198038",
    "#1192e8",
    "#fae100",
    "#0f7cd6",
    "#ff6f61",
    "#9f1853",
    "#6929c4",
    "#8d8d8d",
    "#3ddbd9",
    "#33b1ff",
    "#ffb6ff",
    "#ffadad",
    "#6f45c5",
]


def _iter_existing_files(paths: Iterable[Path]) -> List[Path]:
    files: List[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            files.extend(sorted(path.rglob("*.csv")))
            files.extend(sorted(path.rglob("*.parquet")))
        else:
            files.append(path)
    return files


def _file_signature(path: Path) -> Tuple[str, float]:
    stat = path.stat()
    return (str(path), stat.st_mtime)


@lru_cache(maxsize=128)
def _load_dataframe(signature: Tuple[str, float]) -> pd.DataFrame:
    path_str, _ = signature
    path = Path(path_str)
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    return df


def _load_cached(path: Path) -> pd.DataFrame:
    return _load_dataframe(_file_signature(path)).copy()


def list_janitza_files() -> List[Path]:
    files = []
    for directory in JANITZA_DIRS:
        if not directory.exists():
            continue
        files.extend(directory.glob("umg*.csv"))
        files.extend(directory.glob("measurements*.csv"))
    return sorted(files)


def list_weather_files() -> Dict[str, Path]:
    files = _iter_existing_files([WEATHER_DIR, FORECASTS_DIR])
    mapping: Dict[str, Path] = {}
    for path in files:
        key = path.stem.lower()
        mapping[key] = path
    return mapping


def _ensure_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"]).set_index("timestamp")
    elif isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
    else:
        raise ValueError("Dataframe does not contain timestamp column or datetime index")
    df = df.sort_index()
    return df


def _infer_unit(column: str) -> str:
    name = column.lower()
    if name.startswith("power_") or name.startswith("p_"):
        return "kW"
    if name.startswith("q_") or "reactive" in name:
        return "kvar"
    if name.startswith("s_") or "apparent" in name:
        return "kVA"
    if "voltage" in name or name.startswith("u"):
        return "V"
    if "current" in name or name.startswith("i"):
        return "A"
    if "freq" in name:
        return "Hz"
    if "pf" in name or "factor" in name:
        return "1"
    if "thd" in name:
        return "%"
    if name.endswith("pct") or "percent" in name:
        return "%"
    if name.endswith("_c"):
        return "°C"
    if name.endswith("_ms"):
        return "m/s"
    if name.endswith("ghi_wm2") or "irradiance" in name:
        return "W/m²"
    return ""


def _clip_today(df: pd.DataFrame, end: datetime) -> pd.DataFrame:
    now_utc = datetime.now(tz=UTC)
    if end.date() >= now_utc.date():
        clip_to = min(now_utc, end)
        df = df.loc[:clip_to]
    return df


def _resample(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.loc[start:end]
    if df.empty:
        return df
    df = df.resample(RESAMPLE_RULE).mean()
    return df


def load_janitza_series(
    start: datetime,
    end: datetime,
    metrics: Sequence[str],
) -> SeriesResponse:
    files = list_janitza_files()
    if not files or not metrics:
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})

    frames: List[pd.DataFrame] = []
    for path in files:
        try:
            df = _ensure_timestamp(_load_cached(path))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Skipping Janitza file %s: %s", path, exc)
            continue
        if df.index.max() < start or df.index.min() > end:
            continue
        frames.append(df)

    if not frames:
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})

    merged = pd.concat(frames).sort_index()
    merged = merged.loc[start:end]
    merged = _clip_today(merged, end)
    if merged.empty:
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})

    merged = _resample(merged, start, end)
    merged = merged.loc[:, [col for col in metrics if col in merged.columns]]

    series_data: List[SeriesPayload] = []
    for idx, column in enumerate(merged.columns):
        unit = _infer_unit(column)
        color = PALETTE[idx % len(PALETTE)]
        points = [
            SeriesPoint(timestamp=int(ts.timestamp() * 1000), value=(None if pd.isna(val) else float(val)))
            for ts, val in merged[column].items()
        ]
        series_data.append(SeriesPayload(name=column, unit=unit, color=color, data=points))

    return SeriesResponse(
        series=series_data,
        meta={"from": start.isoformat(), "to": end.isoformat(), "rows": len(merged)},
    )


def load_janitza_latest(
    start: datetime,
    end: datetime,
    metrics: Sequence[str],
) -> List[MetricRow]:
    files = list_janitza_files()
    frames: List[pd.DataFrame] = []
    for path in files:
        try:
            df = _ensure_timestamp(_load_cached(path))
        except Exception:
            continue
        frames.append(df)
    if not frames:
        return []
    merged = pd.concat(frames).sort_index()
    merged = merged.loc[start:end]
    merged = _clip_today(merged, end)
    if merged.empty:
        return []
    rows: List[MetricRow] = []
    latest = merged.tail(1)
    for column in metrics:
        if column not in latest.columns:
            continue
        value = latest[column].iloc[0]
        unit = _infer_unit(column)
        rows.append(MetricRow(metric=column, value=None if pd.isna(value) else float(value), unit=unit))
    return rows


def resolve_weather_selection(selection: str) -> Optional[Path]:
    mapping = list_weather_files()
    key = selection.lower()
    if key.startswith("file:"):
        key = key.split(":", 1)[1]
    if key in mapping:
        return mapping[key]
    # sensible defaults
    for candidate in ("nowcast", "hourly", "48h", "day-ahead"):
        if candidate in mapping and candidate.startswith(key):
            return mapping[candidate]
    return None


def load_weather_series(
    selection: str,
    start: datetime,
    end: datetime,
) -> SeriesResponse:
    path = resolve_weather_selection(selection)
    if not path:
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})
    try:
        df = _ensure_timestamp(_load_cached(path))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed to load weather %s: %s", path, exc)
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})

    df = df.loc[start:end]
    df = _clip_today(df, end)
    if df.empty:
        return SeriesResponse(series=[], meta={"from": start.isoformat(), "to": end.isoformat(), "rows": 0})

    # Normalize common fields
    rename_map = {
        "temperature": "temp_C",
        "temperature_2m": "temp_C",
        "temp": "temp_C",
        "windspeed": "wind_ms",
        "windspeed_10m": "wind_ms",
        "wind_speed": "wind_ms",
        "wind_ms": "wind_ms",
        "cloudcover": "clouds_pct",
        "cloud_cover": "clouds_pct",
        "clouds_pct": "clouds_pct",
        "ghi": "ghi_Wm2",
        "ghi_wm2": "ghi_Wm2",
        "solar_ghi": "ghi_Wm2",
        "forecast_power": "forecast_power_W",
    }
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    df = _resample(df, start, end).ffill()
    df = df.loc[:, [col for col in df.columns if df[col].dtype.kind in "if"]]

    series_data: List[SeriesPayload] = []
    for idx, column in enumerate(df.columns):
        unit = _infer_unit(column)
        color = PALETTE[idx % len(PALETTE)]
        points = [
            SeriesPoint(timestamp=int(ts.timestamp() * 1000), value=(None if pd.isna(val) else float(val)))
            for ts, val in df[column].items()
        ]
        series_data.append(SeriesPayload(name=column, unit=unit, color=color, data=points))

    return SeriesResponse(
        series=series_data,
        meta={"from": start.isoformat(), "to": end.isoformat(), "rows": len(df)},
    )


def default_window(range_name: str) -> Tuple[datetime, datetime]:
    now = datetime.now(tz=UTC)
    if range_name == "3days":
        start = now - timedelta(days=3)
    elif range_name == "week":
        start = now - timedelta(days=7)
    elif range_name == "month":
        start = now - timedelta(days=30)
    elif range_name == "year":
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=1)
    return start, now


def discover_metric_columns() -> List[str]:
    files = list_janitza_files()
    if not files:
        return []
    latest = files[-1]
    try:
        df = _load_cached(latest)
        if "timestamp" in df.columns:
            df = df.drop(columns=["timestamp"])
        return list(df.columns)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unable to discover metric columns: %s", exc)
        return []
