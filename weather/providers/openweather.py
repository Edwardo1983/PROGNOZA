"""OpenWeather One Call provider."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema
from ..normalize import normalize_openweather


class OpenWeatherProvider(Provider):
    API_ENDPOINT = "https://api.openweathermap.org/data/3.0/onecall"

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        api_key: Optional[str] = None,
        units: str = "metric",
        ttl: int = 1800,
        priority: int = 100,
        cache=None,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        retries: int = 3,
        backoff: float = 1.0,
    ) -> None:
        super().__init__(
            "openweather",
            priority=priority,
            cache=cache,
            ttl=ttl,
            ttl_scopes={"hourly": ttl},
            session=session,
        )
        self.latitude = latitude
        self.longitude = longitude
        self.units = units
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.session = session or requests.Session()
        self.base_url = base_url or self.API_ENDPOINT
        self.retries = retries
        self.backoff = backoff

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        start_ts = self._as_utc_timestamp(start)
        end_ts = self._as_utc_timestamp(end)

        def _fetch() -> pd.DataFrame:
            payload = self._request()
            frame = normalize_openweather(payload)
            if frame.empty:
                return frame
            mask = (frame.index >= start_ts) & (frame.index <= end_ts)
            return frame.loc[mask]

        frame = self.fetch_with_cache(
            "hourly",
            {"lat": self.latitude, "lon": self.longitude},
            _fetch,
            ttl=self.ttl_for("hourly", fallback=1800),
        )
        frame = ensure_schema(frame)
        mask = (frame.index >= start_ts) & (frame.index <= end_ts)
        filtered = frame.loc[mask]
        metadata = {
            "source": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "units": self.units,
        }
        return ForecastFrame(filtered, metadata)

    def _request(self) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENWEATHER_API_KEY is not configured")

        params = {
            "lat": self.latitude,
            "lon": self.longitude,
            "appid": self.api_key,
            "units": self.units,
            "exclude": "minutely,daily,alerts",
        }
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - network failure
                last_exc = exc
                time.sleep(self.backoff * attempt)
                continue
        raise RuntimeError(f"OpenWeather request failed after {self.retries} attempts: {last_exc}")

    @staticmethod
    def _as_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tz is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
