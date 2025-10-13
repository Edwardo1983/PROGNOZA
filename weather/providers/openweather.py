"""OpenWeather One Call provider."""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema
from ..normalize import normalize_openweather

logger = logging.getLogger(__name__)


class OpenWeatherProvider(Provider):
    API_ENDPOINT = "https://api.openweathermap.org/data/3.0/onecall"
    API_ENDPOINT_V25 = "https://api.openweathermap.org/data/2.5/onecall"

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
        skip_on_auth_failure: bool = True,
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
        self.skip_on_auth_failure = skip_on_auth_failure
        self._auth_failure_logged = False

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

        params: Dict[str, Any] = {
            "lat": self.latitude,
            "lon": self.longitude,
            "appid": self.api_key,
            "units": self.units,
            "exclude": "minutely,daily,alerts",
        }

        primary_url = self.base_url or self.API_ENDPOINT
        fallbacks = []
        if primary_url.rstrip("/") != self.API_ENDPOINT_V25:
            fallbacks.append(self.API_ENDPOINT_V25)
        endpoints = [primary_url, *fallbacks]
        tried_urls: list[str] = []

        for url in endpoints:
            tried_urls.append(url)
            auth_error: Optional[tuple[int, str]] = None
            last_exc: Optional[Exception] = None

            for attempt in range(1, self.retries + 1):
                try:
                    response = self.session.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    return response.json()
                except requests.HTTPError as exc:
                    status = self._status_code(exc)
                    detail = self._http_error_detail(exc)
                    if status in (401, 403):
                        auth_error = (status, detail)
                        break
                    last_exc = exc
                except Exception as exc:  # pragma: no cover - network failure
                    last_exc = exc
                time.sleep(self.backoff * attempt)

            if auth_error is not None:
                status, detail = auth_error
                if url != endpoints[-1]:
                    logger.warning(
                        "OpenWeather endpoint %s responded with %s%s; retrying with legacy API",
                        url,
                        status,
                        detail,
                    )
                    continue
                if self.skip_on_auth_failure:
                    if not self._auth_failure_logged:
                        logger.error(
                            "OpenWeather authentication failed with status %s%s; skipping provider until restart",
                            status,
                            detail,
                        )
                        self._auth_failure_logged = True
                    return {"current": None, "hourly": []}
                raise RuntimeError(
                    f"OpenWeather rejected the API key with status {status}{detail}. "
                    "Update OPENWEATHER_API_KEY or disable the provider."
                )

            if last_exc is not None:
                if url != endpoints[-1]:
                    logger.warning(
                        "OpenWeather endpoint %s failed (%s); retrying with legacy API",
                        url,
                        last_exc,
                    )
                    continue
                raise RuntimeError(
                    f"OpenWeather request failed after {self.retries} attempts for {url}: {last_exc}"
                ) from last_exc

        raise RuntimeError(f"OpenWeather request failed for endpoints: {', '.join(tried_urls)}")

    @staticmethod
    def _http_error_detail(exc: requests.HTTPError) -> str:
        response = exc.response
        detail: Optional[str] = None
        if response is not None:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                detail = payload.get("message") or payload.get("msg") or payload.get("error")
            if not detail:
                text = response.text.strip()
                detail = text if text else None
        if not detail:
            match = re.search(r"Client Error:\s*(.*)", str(exc))
            if match:
                extracted = match.group(1).strip()
                if extracted:
                    detail = extracted
        return f": {detail}" if detail else ""

    @staticmethod
    def _status_code(exc: requests.HTTPError) -> Optional[int]:
        response = exc.response
        if response is not None:
            raw = getattr(response, "status_code", None)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
        match = re.search(r"(\d{3})\s+[A-Za-z]+ Error", str(exc))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _as_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tz is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
