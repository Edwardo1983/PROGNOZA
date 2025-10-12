from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from weather.cache import WeatherCache
from weather.core import ForecastFrame, Provider, REQUIRED_COLUMNS
from weather.router import WeatherRouter


class StaticProvider(Provider):
    def __init__(
        self,
        name: str,
        frame: pd.DataFrame,
        *,
        priority: int,
        nowcast: pd.DataFrame | None = None,
        cache_path: Path | None = None,
    ):
        cache = WeatherCache(cache_path) if cache_path else WeatherCache(Path(f".cache/{name}.sqlite"))
        super().__init__(name, priority=priority, cache=cache)
        self._frame = frame
        self._nowcast = nowcast

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        start_ts = _as_utc(start)
        end_ts = _as_utc(end)
        mask = (self._frame.index >= start_ts) & (self._frame.index <= end_ts)
        return ForecastFrame(self._frame.loc[mask].copy())

    def supports_nowcast(self) -> bool:
        return self._nowcast is not None

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        if self._nowcast is None:
            return ForecastFrame(self._frame.iloc[0:0].copy())
        now = self._nowcast.index.min()
        horizon = now + pd.Timedelta(hours=next_hours)
        mask = (self._nowcast.index >= now - pd.Timedelta(minutes=30)) & (self._nowcast.index <= horizon)
        return ForecastFrame(self._nowcast.loc[mask].copy())


def _build_frame(values: list[float | None], idx: pd.DatetimeIndex) -> pd.DataFrame:
    data = {col: values for col in REQUIRED_COLUMNS}
    frame = pd.DataFrame(data, index=idx, dtype=float)
    return frame


def _as_utc(value: datetime | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tz is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def test_router_merges_priority(tmp_path: Path) -> None:
    idx = pd.date_range("2024-01-01T00:00Z", periods=3, freq="h", tz="UTC")
    primary_values = [1.0, 2.0, np.nan]
    secondary_values = [10.0, 11.0, 12.0]
    primary_frame = _build_frame(primary_values, idx)
    secondary_frame = _build_frame(secondary_values, idx)

    primary = StaticProvider("primary", primary_frame, priority=10, cache_path=tmp_path / "primary.sqlite")
    backup = StaticProvider("backup", secondary_frame, priority=20, cache_path=tmp_path / "backup.sqlite")
    router = WeatherRouter([backup, primary], tz="Europe/Bucharest")

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    merged = router.get_hourly(start, end)

    assert merged.loc[idx[0], "temp_C"] == primary_values[0]
    assert merged.loc[idx[2], "temp_C"] == secondary_values[2]
    assert merged.loc[idx[2], "source"] == "backup"


def test_nowcast_resample_and_source(tmp_path: Path) -> None:
    now = pd.Timestamp("2024-01-01T00:00Z")
    idx_primary = pd.date_range(now, periods=5, freq="10min", tz="UTC")
    idx_backup = pd.date_range(now, periods=3, freq="15min", tz="UTC")
    primary_nowcast = _build_frame([5.0, 5.1, np.nan, np.nan, np.nan], idx_primary)
    backup_nowcast = _build_frame([6.0, 6.1, 6.2], idx_backup)

    primary = StaticProvider(
        "primary",
        primary_nowcast,
        priority=10,
        nowcast=primary_nowcast,
        cache_path=tmp_path / "primary.sqlite",
    )
    backup = StaticProvider(
        "backup",
        backup_nowcast,
        priority=20,
        nowcast=backup_nowcast,
        cache_path=tmp_path / "backup.sqlite",
    )

    router = WeatherRouter([primary, backup], tz="Europe/Bucharest")
    frame = router.get_nowcast(next_hours=1)

    assert not frame.empty
    deltas = frame.index.to_series().diff().dropna().unique()
    assert all(delta == pd.Timedelta(minutes=15) for delta in deltas)
    assert frame["source"].iloc[0] == "primary"
