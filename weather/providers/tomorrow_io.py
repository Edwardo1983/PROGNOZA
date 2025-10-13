"""Tomorrow.io weather provider."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema, resample_frame
from ..normalize import normalize_tomorrow


class TomorrowIOProvider(Provider):
    API_ENDPOINT = "https://api.tomorrow.io/v4/timelines"

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        api_key: Optional[str] = None,
        ttl: int = 1800,
        priority: int = 140,
        cache=None,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        retries: int = 3,
        backoff: float = 1.0,
        skip_on_auth_failure: bool = True,
    ) -> None:
        super().__init__(
            "tomorrow_io",
            priority=priority,
            cache=cache,
            ttl=ttl,
            ttl_scopes={"hourly": ttl, "nowcast": ttl},
            session=session,
        )
        self.latitude = latitude
        self.longitude = longitude
        self.api_key = api_key or os.getenv("TOMORROW_IO_API_KEY") or os.getenv("TOMORROWIO_API_KEY")
        self.session = session or requests.Session()
        self.base_url = base_url or self.API_ENDPOINT
        self.retries = retries
        self.backoff = backoff
        self.skip_on_auth_failure = skip_on_auth_failure
        self._auth_failure_logged = False
        self._permanently_disabled = False

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        # Skip provider if permanently disabled due to auth failure
        if self._permanently_disabled:
            from ..normalize import empty_frame
            return ForecastFrame(empty_frame(), {"source": self.name, "skipped": True})

        start_ts = self._as_utc(start)
        end_ts = self._as_utc(end)

        def _fetch() -> pd.DataFrame:
            payload = self._request(start_ts, end_ts, "1h")
            frame = normalize_tomorrow(payload)
            return frame.loc[(frame.index >= start_ts) & (frame.index <= end_ts)]

        frame = self.fetch_with_cache(
            "hourly",
            {"lat": self.latitude, "lon": self.longitude, "timestep": "1h"},
            _fetch,
            ttl=self.ttl_for("hourly", fallback=1800),
        )
        frame = ensure_schema(frame)
        frame = frame.loc[(frame.index >= start_ts) & (frame.index <= end_ts)]
        metadata = {
            "source": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }
        return ForecastFrame(frame, metadata)

    def supports_nowcast(self) -> bool:
        return True

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        # Skip provider if permanently disabled due to auth failure
        if self._permanently_disabled:
            from ..normalize import empty_frame
            return ForecastFrame(empty_frame(), {"source": self.name, "skipped": True})

        now_utc = pd.Timestamp.now(tz="UTC")
        horizon = now_utc + pd.Timedelta(hours=next_hours)

        def _fetch() -> pd.DataFrame:
            payload = self._request(now_utc - pd.Timedelta(minutes=15), horizon, "15m")
            frame = normalize_tomorrow(payload)
            return frame.loc[(frame.index >= now_utc - pd.Timedelta(minutes=15)) & (frame.index <= horizon)]

        frame = self.fetch_with_cache(
            "nowcast",
            {"lat": self.latitude, "lon": self.longitude, "timestep": "15m"},
            _fetch,
            ttl=self.ttl_for("nowcast", fallback=900),
        )
        frame = ensure_schema(frame)
        window = frame.loc[(frame.index >= now_utc - pd.Timedelta(minutes=15)) & (frame.index <= horizon)]
        resampled = resample_frame(window, "15min", method="interpolate")
        return ForecastFrame(resampled, {"source": self.name})

    def _request(self, start: pd.Timestamp, end: pd.Timestamp, timestep: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("TOMORROW_IO_API_KEY is not configured")

        payload = {
            "location": {"type": "Point", "coordinates": [self.longitude, self.latitude]},
            "fields": [
                "temperature",
                "windSpeed",
                "windDirection",
                "cloudCover",
                "humidity",
                "uvIndex",
                "solarGHI",
            ],
            "timesteps": [timestep],
            "startTime": start.isoformat(),
            "endTime": end.isoformat(),
            "timezone": "UTC",
        }
        params = {"apikey": self.api_key}
        headers = {"Accept": "application/json"}

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.post(self.base_url, params=params, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                json_data = response.json()
                # Validate that response contains expected structure
                if not isinstance(json_data, dict):
                    raise ValueError("API response is not a valid JSON object")
                return json_data
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response else None
                if status_code in (401, 403) and self.skip_on_auth_failure:
                    if not self._auth_failure_logged:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(
                            "Tomorrow.io authentication failed with status %s; provider disabled. "
                            "To use Tomorrow.io, obtain a valid API key from https://www.tomorrow.io/weather-api/",
                            status_code,
                        )
                        self._auth_failure_logged = True
                        self._permanently_disabled = True
                    return {"data": {"timelines": []}}
                last_exc = exc
                time.sleep(self.backoff * attempt)
            except Exception as exc:  # pragma: no cover - network failure
                last_exc = exc
                time.sleep(self.backoff * attempt)
                continue
        raise RuntimeError(f"Tomorrow.io request failed after {self.retries} attempts: {last_exc}")

    @staticmethod
    def _as_utc(value: datetime | pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tz is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
