from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from weather.cache import WeatherCache
from weather.core import REQUIRED_COLUMNS
from weather.providers.openmeteo_ecmwf import OpenMeteoECMWFProvider
from weather.providers.openweather import OpenWeatherProvider


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return DummyResponse(self.payload)


def _hourly_window(hours: int) -> tuple[datetime, datetime]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=hours)
    return start, end


def test_openweather_normalization_and_cache(tmp_path: Path) -> None:
    session = DummySession(
        {
            "current": {
                "dt": 1704067200,
                "temp": 5.0,
                "wind_speed": 3.0,
                "wind_deg": 120,
                "clouds": 80,
                "humidity": 75,
                "uvi": 0.5,
            },
            "hourly": [
                {
                    "dt": 1704070800,
                    "temp": 6.0,
                    "wind_speed": 2.5,
                    "wind_deg": 110,
                    "clouds": 60,
                    "humidity": 65,
                    "uvi": 0.6,
                }
            ],
        }
    )
    cache = WeatherCache(tmp_path / "ow_cache.sqlite")
    provider = OpenWeatherProvider(
        latitude=44.4,
        longitude=26.1,
        api_key="test",
        cache=cache,
        session=session,
        ttl=3600,
    )
    start, end = _hourly_window(2)
    frame = provider.get_hourly(start, end).ensure_schema().data
    assert set(REQUIRED_COLUMNS).issubset(frame.columns)
    assert frame.index.tz is not None
    assert not frame.empty
    # Second call should use cache
    provider.get_hourly(start, end)
    assert session.calls == 1


def test_openmeteo_conversion(tmp_path: Path) -> None:
    timestamps = ["2024-01-01T00:00", "2024-01-01T01:00"]
    payload = {
        "hourly": {
            "time": timestamps,
            "temperature_2m": [4.0, 5.5],
            "windspeed_10m": [18.0, 21.6],
            "winddirection_10m": [200, 210],
            "cloudcover": [70, 65],
            "relativehumidity_2m": [80, 78],
            "uv_index": [0.2, 0.3],
            "shortwave_radiation": [120.0, 150.0],
        },
        "hourly_units": {
            "windspeed_10m": "km/h",
        },
    }
    session = DummySession(payload)
    cache = WeatherCache(tmp_path / "om_cache.sqlite")
    provider = OpenMeteoECMWFProvider(
        latitude=44.4,
        longitude=26.1,
        models=["ecmwf"],
        cache=cache,
        session=session,
        ttl=3600,
    )
    start, end = _hourly_window(2)
    frame = provider.get_hourly(start, end).ensure_schema().data
    assert set(REQUIRED_COLUMNS).issubset(frame.columns)
    assert np.isclose(frame.iloc[0]["wind_ms"], 5.0)
    provider.get_hourly(start, end)
    assert session.calls == 1
