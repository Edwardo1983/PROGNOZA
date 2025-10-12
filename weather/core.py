"""Core abstractions for the weather package."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .cache import WeatherCache
    from requests import Session as RequestsSession
else:  # pragma: no cover - used only for typing
    WeatherCache = Any  # type: ignore[assignment]
    RequestsSession = Any  # type: ignore[assignment]

SessionLike = RequestsSession

DEFAULT_RESAMPLE_METHOD = "nearest"
REQUIRED_COLUMNS: Sequence[str] = (
    "temp_C",
    "wind_ms",
    "wind_deg",
    "clouds_pct",
    "humidity",
    "uvi",
    "ghi_Wm2",
)


def ensure_utc_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with a timezone-aware UTC index sorted ascending."""
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Forecast frames must be indexed by pandas.DatetimeIndex")

    working = frame.copy()
    idx = working.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")

    working.index = idx
    working = working.sort_index()
    return working


def ensure_schema(frame: pd.DataFrame) -> pd.DataFrame:
    """Enforce the standard schema for forecast frames."""
    working = ensure_utc_index(frame)
    columns = list(REQUIRED_COLUMNS)
    for column in columns:
        if column not in working.columns:
            working[column] = np.nan
    return working.loc[:, columns]


def align_frames(frames: Iterable[pd.DataFrame]) -> pd.DatetimeIndex:
    """Return the union of all indices in UTC for downstream alignment."""
    indices = [ensure_utc_index(frame).index for frame in frames if not frame.empty]
    if not indices:
        return pd.DatetimeIndex([], tz="UTC")
    union = indices[0]
    for idx in indices[1:]:
        union = union.union(idx)
    return union.sort_values()


def resample_frame(
    frame: pd.DataFrame,
    freq: str,
    method: str = DEFAULT_RESAMPLE_METHOD,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Resample data to a uniform frequency with time-aware interpolation."""
    if frame.empty:
        return frame
    working = ensure_schema(frame).copy()
    resampler = working.resample(freq)
    if method == "nearest":
        resampled = resampler.nearest(limit=limit)
    elif method == "pad":
        resampled = resampler.pad(limit=limit)
    elif method == "interpolate":
        resampled = resampler.interpolate(method="time", limit=limit)
    else:
        raise ValueError(f"Unsupported resample method '{method}'")
    return ensure_schema(resampled)


def to_local(frame: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Convert a UTC-indexed DataFrame to the configured local timezone."""
    working = ensure_utc_index(frame)
    zone = ZoneInfo(tz)
    localized = working.copy()
    localized.index = localized.index.tz_convert(zone)
    return localized


@dataclass
class ForecastFrame:
    """Wrapper containing normalized forecast data and auxiliary metadata."""

    data: pd.DataFrame
    metadata: Dict[str, Any] = field(default_factory=dict)

    def ensure_schema(self) -> "ForecastFrame":
        self.data = ensure_schema(self.data)
        return self

    def empty(self) -> bool:
        return self.data.empty


class Provider(ABC):
    """Base class for all weather providers."""

    name: str

    def __init__(
        self,
        name: str,
        *,
        priority: int = 100,
        cache: Optional[WeatherCache] = None,
        ttl: Optional[int] = None,
        ttl_scopes: Optional[Dict[str, int]] = None,
        session: Optional[SessionLike] = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self._ttl_default = ttl
        self._ttl_scopes = ttl_scopes or {}
        self.session = session
        if cache is None:
            from .cache import WeatherCache

            cache = WeatherCache.default()
        self.cache = cache

    def ttl_for(self, scope: str, fallback: Optional[int] = None) -> Optional[int]:
        if scope in self._ttl_scopes:
            return self._ttl_scopes[scope]
        if fallback is not None:
            return fallback
        return self._ttl_default

    def supports_nowcast(self) -> bool:
        return False

    def fetch_with_cache(
        self,
        scope: str,
        key: Dict[str, Any],
        fetcher: Callable[[], pd.DataFrame],
        ttl: Optional[int] = None,
    ) -> pd.DataFrame:
        cache_key = json.dumps(key, sort_keys=True)
        ttl_seconds = ttl if ttl is not None else self.ttl_for(scope)
        if ttl_seconds:
            cached = self.cache.get(self.name, scope, cache_key)
            if cached is not None:
                return cached
        data = fetcher()
        if ttl_seconds and not data.empty:
            self.cache.set(self.name, scope, cache_key, data, ttl_seconds)
        return data

    @abstractmethod
    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        """Return hourly forecast between UTC boundaries."""

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        """Return sub-hourly nowcast data when supported."""
        raise NotImplementedError(f"{self.name} does not implement nowcast")
