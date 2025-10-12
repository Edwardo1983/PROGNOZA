"""Open-Meteo ECMWF/Icon provider."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema, resample_frame
from ..normalize import normalize_openmeteo


class OpenMeteoECMWFProvider(Provider):
    API_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        *,
        latitude: float,
        longitude: float,
        models: Optional[Iterable[str]] = None,
        ttl: int = 1800,
        priority: int = 120,
        cache=None,
        session: Optional[requests.Session] = None,
        retries: int = 3,
        backoff: float = 1.0,
        timezone: str = "UTC",
    ) -> None:
        super().__init__(
            "openmeteo_ecmwf",
            priority=priority,
            cache=cache,
            ttl=ttl,
            ttl_scopes={"hourly": ttl},
            session=session,
        )
        self.latitude = latitude
        self.longitude = longitude
        self.models = list(models or ["ecmwf"])
        self.session = session or requests.Session()
        self.retries = retries
        self.backoff = backoff
        self.timezone = timezone

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        start_ts = self._as_utc_timestamp(start)
        end_ts = self._as_utc_timestamp(end)

        def _fetch() -> pd.DataFrame:
            payload = self._request()
            frame = normalize_openmeteo(payload)
            mask = (frame.index >= start_ts) & (frame.index <= end_ts)
            return frame.loc[mask]

        frame = self.fetch_with_cache(
            "hourly",
            {"lat": self.latitude, "lon": self.longitude, "models": self.models},
            _fetch,
            ttl=self.ttl_for("hourly", fallback=3600),
        )
        frame = ensure_schema(frame)
        mask = (frame.index >= start_ts) & (frame.index <= end_ts)
        filtered = frame.loc[mask]
        return ForecastFrame(
            filtered,
            {
                "source": self.name,
                "models": self.models,
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
        )

    def supports_nowcast(self) -> bool:
        return True

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        now_utc = pd.Timestamp.utcnow().tz_localize("UTC")
        horizon = now_utc + pd.Timedelta(hours=next_hours)

        payload = self._request()
        frame = normalize_openmeteo(payload)
        if frame.empty:
            return ForecastFrame(frame, {"source": self.name})

        window = frame.loc[(frame.index >= now_utc - pd.Timedelta(hours=1)) & (frame.index <= horizon)]
        resampled = resample_frame(window, "15min", method="interpolate")
        resampled = resampled.loc[resampled.index <= horizon]
        return ForecastFrame(resampled, {"source": self.name})

    def _request(self) -> Dict[str, Any]:
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "windspeed_10m",
                    "winddirection_10m",
                    "cloudcover",
                    "relativehumidity_2m",
                    "uv_index",
                    "shortwave_radiation",
                ]
            ),
            "timezone": self.timezone,
        }
        if self.models:
            params["models"] = ",".join(self.models)

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(self.API_ENDPOINT, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - network failure
                last_exc = exc
                time.sleep(self.backoff * attempt)
                continue
        raise RuntimeError(f"Open-Meteo request failed after {self.retries} attempts: {last_exc}")

    @staticmethod
    def _as_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tz is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
