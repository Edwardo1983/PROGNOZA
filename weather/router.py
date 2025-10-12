"""Routing and orchestration for weather providers."""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import yaml

from .core import Provider, REQUIRED_COLUMNS, align_frames, ensure_schema, resample_frame, to_local
from .cache import WeatherCache
from .normalize import empty_frame
from .providers.openmeteo_ecmwf import OpenMeteoECMWFProvider
from .providers.openweather import OpenWeatherProvider
from .providers.tomorrow_io import TomorrowIOProvider


def load_weather_config(path: Optional[Path | str] = None) -> Dict[str, object]:
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path("config") / "weather.yaml")
    candidates.append(Path("config") / "weather.yml")
    for candidate in candidates:
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle) or {}
    return {}


def build_providers(
    config: Dict[str, object],
    *,
    cache_path: Optional[Path] = None,
) -> List[Provider]:
    providers_cfg = config.get("providers", [])
    if not providers_cfg:
        return []
    cache = WeatherCache(cache_path) if cache_path else WeatherCache.default()
    shared = config.get("location", {})
    lat = shared.get("lat") or shared.get("latitude")
    lon = shared.get("lon") or shared.get("longitude")

    instantiated: List[Provider] = []
    for entry in providers_cfg:
        provider_type = entry.get("type")
        priority = int(entry.get("priority", 100))
        ttl = entry.get("ttl") or entry.get("ttl_seconds")
        ttl_seconds = int(ttl) if ttl is not None else None
        if provider_type == "openweather":
            api_key = entry.get("api_key") or os.getenv("OPENWEATHER_API_KEY")
            instantiated.append(
                OpenWeatherProvider(
                    latitude=float(entry.get("lat", lat)),
                    longitude=float(entry.get("lon", lon)),
                    api_key=api_key,
                    units=entry.get("units", "metric"),
                    ttl=ttl_seconds or 1800,
                    priority=priority,
                    cache=cache,
                )
            )
        elif provider_type == "openmeteo_ecmwf":
            models = entry.get("models")
            instantiated.append(
                OpenMeteoECMWFProvider(
                    latitude=float(entry.get("lat", lat)),
                    longitude=float(entry.get("lon", lon)),
                    models=models,
                    ttl=ttl_seconds or 3600,
                    priority=priority,
                    cache=cache,
                    timezone=config.get("timezone", "UTC"),
                )
            )
        elif provider_type == "tomorrow_io":
            api_key = entry.get("api_key") or os.getenv("TOMORROW_IO_API_KEY") or os.getenv("TOMORROWIO_API_KEY")
            instantiated.append(
                TomorrowIOProvider(
                    latitude=float(entry.get("lat", lat)),
                    longitude=float(entry.get("lon", lon)),
                    api_key=api_key,
                    ttl=ttl_seconds or 900,
                    priority=priority,
                    cache=cache,
                )
            )
        else:
            raise ValueError(f"Unsupported provider type '{provider_type}'")
    return instantiated


class WeatherRouter:
    """Query multiple providers and merge forecasts according to priority."""

    def __init__(self, sources: Sequence[Provider], tz: str = "UTC") -> None:
        self.sources = sorted(sources, key=lambda p: p.priority)
        self.tz = tz

    def get_hourly(self, start: datetime, end: datetime) -> pd.DataFrame:
        start_ts = _as_utc_timestamp(start)
        end_ts = _as_utc_timestamp(end)
        frames: List[Tuple[str, pd.DataFrame]] = []
        for provider in self.sources:
            forecast = provider.get_hourly(start_ts.to_pydatetime(), end_ts.to_pydatetime())
            df = forecast.ensure_schema().data
            df = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]
            if df.empty:
                continue
            df = ensure_schema(df)
            frames.append((provider.name, df))
        merged = _merge(frames)
        if merged.empty:
            return merged
        merged = merged.loc[(merged.index >= start_ts) & (merged.index <= end_ts)]
        return merged

    def get_nowcast(self, next_hours: int = 2) -> pd.DataFrame:
        frames: List[Tuple[str, pd.DataFrame]] = []
        for provider in self.sources:
            if not provider.supports_nowcast():
                continue
            forecast = provider.get_nowcast(next_hours)
            df = forecast.ensure_schema().data
            if df.empty:
                continue
            frames.append((provider.name, df))
        merged = _merge(frames)
        if merged.empty:
            return merged
        numeric = merged[list(REQUIRED_COLUMNS)]
        resampled = resample_frame(numeric, "15min", method="interpolate")
        sources = merged["source"].reindex(resampled.index, method="pad")
        resampled["source"] = sources
        return resampled

    def to_local(self, frame: pd.DataFrame) -> pd.DataFrame:
        return to_local(frame, self.tz)


def _merge(frames: Sequence[Tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    if not frames:
        empty = empty_frame()
        empty["source"] = pd.Series(dtype="object")
        return empty

    indices = [frame for _, frame in frames]
    union = align_frames(indices)
    result = pd.DataFrame(index=union, columns=list(REQUIRED_COLUMNS), dtype=float)
    source = pd.Series(index=union, dtype="object")

    for name, frame in frames:
        aligned = frame.reindex(union)
        row_mask = aligned.notna().any(axis=1)
        for column in REQUIRED_COLUMNS:
            current = result[column]
            incoming = aligned[column]
            fill_mask = current.isna() & incoming.notna()
            result.loc[fill_mask, column] = incoming.loc[fill_mask]
        source_fill = row_mask & source.isna()
        source.loc[source_fill] = name

    result["source"] = source
    return result


def _as_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def write_output(frame: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix.lower()
    if suffix == ".parquet":
        try:
            frame.to_parquet(out_path)
        except ImportError:  # pragma: no cover - handled at runtime if pyarrow missing
            csv_path = out_path.with_suffix(".csv")
            frame.to_csv(csv_path)
    elif suffix in (".csv", ".txt"):
        frame.to_csv(out_path)
    else:
        frame.to_pickle(out_path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Weather router CLI")
    parser.add_argument("--hourly", type=int, help="Fetch N hours of hourly forecast")
    parser.add_argument("--nowcast", type=int, help="Fetch nowcast horizon in hours")
    parser.add_argument("--out", type=Path, required=True, help="Output file path (.parquet or .csv)")
    parser.add_argument("--config", type=Path, help="Path to weather YAML config")
    args = parser.parse_args(argv)

    if args.hourly is None and args.nowcast is None:
        parser.error("Specify --hourly or --nowcast")

    config = load_weather_config(args.config)
    providers = build_providers(config)
    if not providers:
        raise SystemExit("No providers configured")

    router = WeatherRouter(providers, tz=config.get("timezone", "UTC"))
    now = pd.Timestamp.utcnow().tz_localize("UTC")

    if args.hourly is not None:
        horizon = now + pd.Timedelta(hours=args.hourly)
        frame = router.get_hourly(now.to_pydatetime(), horizon.to_pydatetime())
    else:
        frame = router.get_nowcast(args.nowcast or 2)

    write_output(frame, args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
