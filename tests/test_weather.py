"""Tests for the weather orchestration layer."""

from __future__ import annotations

import pandas as pd

from tests.conftest import get_test_logger
from tests.helpers import FakeProvider

from weather.router import WeatherRouter

logger = get_test_logger(__name__)
logger.info("Starting tests for weather module")


def _hourly_builder(start: pd.Timestamp, end: pd.Timestamp, calls: dict) -> pd.DataFrame:
    calls["hourly"] = calls.get("hourly", 0) + 1
    idx = pd.date_range(start, end, freq="1h")
    data = {
        "temp_C": [10 + i for i in range(len(idx))],
        "wind_ms": [3.0] * len(idx),
        "wind_deg": [180] * len(idx),
        "clouds_pct": [20 + i for i in range(len(idx))],
        "humidity": [60] * len(idx),
        "uvi": [0.5] * len(idx),
        "ghi_Wm2": [100 + i for i in range(len(idx))],
    }
    return pd.DataFrame(data, index=idx)


def _nowcast_builder(hours: int, calls: dict) -> pd.DataFrame:
    calls["nowcast"] = calls.get("nowcast", 0) + 1
    idx = pd.date_range("2024-01-01T00:00:00Z", periods=hours * 4, freq="15min", tz="UTC")
    data = {
        "temp_C": [5 + i for i in range(len(idx))],
        "wind_ms": [2.5] * len(idx),
        "wind_deg": [90] * len(idx),
        "clouds_pct": [50] * len(idx),
        "humidity": [55] * len(idx),
        "uvi": [0.1] * len(idx),
        "ghi_Wm2": [80] * len(idx),
    }
    return pd.DataFrame(data, index=idx)


def test_weather_router_caching(monkeypatch) -> None:
    """Weather router merges providers and honours cache usage."""
    logger.info("Running weather router test")
    calls: dict[str, int] = {}
    provider = FakeProvider(
        name="fake",
        priority=1,
        hourly_builder=lambda start, end: _hourly_builder(start, end, calls),
        nowcast_builder=lambda hours: _nowcast_builder(hours, calls),
    )
    router = WeatherRouter([provider], tz="Europe/Bucharest")

    start = pd.Timestamp("2024-01-01T00:00:00Z")
    end = start + pd.Timedelta(hours=6)

    hourly = router.get_hourly(start.to_pydatetime(), end.to_pydatetime())
    assert not hourly.empty
    assert list(hourly.columns) == [
        "temp_C",
        "wind_ms",
        "wind_deg",
        "clouds_pct",
        "humidity",
        "uvi",
        "ghi_Wm2",
        "source",
    ]
    assert hourly.index.is_monotonic_increasing

    hourly_cached = router.get_hourly(start.to_pydatetime(), end.to_pydatetime())
    pd.testing.assert_frame_equal(hourly, hourly_cached)
    assert calls["hourly"] == 1, "subsequent hourly fetch should hit cache"

    nowcast = router.get_nowcast(2)
    assert not nowcast.empty
    assert nowcast.index.is_monotonic_increasing

    nowcast_cached = router.get_nowcast(2)
    pd.testing.assert_frame_equal(nowcast, nowcast_cached)
    assert calls["nowcast"] == 1

    local = router.to_local(hourly)
    assert str(local.index.tz) == "Europe/Bucharest"
