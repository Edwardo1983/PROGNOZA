"""OpenWeather provider supporting both One Call and free-plan forecast APIs."""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema, resample_frame
from ..normalize import empty_frame, normalize_openweather

logger = logging.getLogger(__name__)


class OpenWeatherAuthError(RuntimeError):
    """Raised when OpenWeather rejects the API key."""

    def __init__(self, status: Optional[int], detail: str) -> None:
        message = f"OpenWeather authentication failed with status {status}{detail}"
        super().__init__(message)
        self.status = status
        self.detail = detail


class OpenWeatherProvider(Provider):
    API_ENDPOINT = "https://api.openweathermap.org/data/3.0/onecall"
    API_ENDPOINT_V25 = "https://api.openweathermap.org/data/2.5/onecall"
    API_ENDPOINT_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
    API_ENDPOINT_CURRENT = "https://api.openweathermap.org/data/2.5/weather"

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
        api_mode: str = "auto",  # auto | onecall | forecast
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
        self._permanently_disabled = False
        self.api_mode = api_mode.lower()
        self._force_forecast_only = self.api_mode == "forecast"

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        # Skip provider if permanently disabled due to auth failure
        if self._permanently_disabled:
            return ForecastFrame(empty_frame(), {"source": self.name, "skipped": True})

        start_ts = self._as_utc_timestamp(start)
        end_ts = self._as_utc_timestamp(end)

        def _fetch() -> pd.DataFrame:
            mode, payload = self._request()
            if mode == "none" or payload is None:
                return empty_frame()

            frame = normalize_openweather(payload, mode=mode)
            if frame.empty:
                return frame

            if mode == "forecast":
                # Forecast API provides 3-hour increments; resample to hourly for consistency.
                frame = resample_frame(frame, "1h", method="interpolate")

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

    def _request(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        if not self.api_key:
            raise RuntimeError("OPENWEATHER_API_KEY is not configured")

        if self._permanently_disabled:
            return "none", None

        mode = self.api_mode
        if self._force_forecast_only:
            return "forecast", self._request_forecast()

        if mode == "forecast":
            return "forecast", self._request_forecast()

        if mode == "onecall":
            return "onecall", self._request_onecall()

        # Auto-detect: try One Call, fall back to forecast on failure/auth issues.
        try:
            return "onecall", self._request_onecall()
        except OpenWeatherAuthError as exc:
            logger.info(
                "OpenWeather One Call not available (%s%s); falling back to 3-hour forecast API.",
                exc.status,
                exc.detail,
            )
            self._force_forecast_only = True
            return "forecast", self._request_forecast()
        except Exception as exc:  # pragma: no cover - network or API failure
            logger.warning("OpenWeather One Call request failed (%s); using forecast API instead.", exc)
            self._force_forecast_only = True
            return "forecast", self._request_forecast()

    def _request_onecall(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "lat": self.latitude,
            "lon": self.longitude,
            "appid": self.api_key,
            "units": self.units,
            "exclude": "minutely,daily,alerts",
        }
        primary_url = self.base_url or self.API_ENDPOINT
        endpoints = [primary_url]
        tried_urls: List[str] = []

        for url in endpoints:
            tried_urls.append(url)
            auth_error: Optional[Tuple[int, str]] = None
            last_exc: Optional[Exception] = None

            for attempt in range(1, self.retries + 1):
                try:
                    response = self.session.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    json_data = response.json()
                    # Validate that response contains expected structure
                    if not isinstance(json_data, dict):
                        raise ValueError("API response is not a valid JSON object")
                    return json_data
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
                        "OpenWeather endpoint %s responded with %s%s; retrying alternative endpoint",
                        url,
                        status,
                        detail,
                    )
                    continue
                raise OpenWeatherAuthError(status, detail)

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

    def _request_forecast(self) -> Dict[str, Any]:
        params = {
            "lat": self.latitude,
            "lon": self.longitude,
            "appid": self.api_key,
            "units": self.units,
        }
        try:
            forecast = self._request_with_retries(self.API_ENDPOINT_FORECAST, params)
            current = self._request_with_retries(self.API_ENDPOINT_CURRENT, params)
        except OpenWeatherAuthError:
            if self.skip_on_auth_failure:
                if not self._auth_failure_logged:
                    logger.error(
                        "OpenWeather forecast API rejected the key; provider disabled until restart. "
                        "Verify the key at https://openweathermap.org/price",
                    )
                    self._auth_failure_logged = True
                self._permanently_disabled = True
                return {"current": None, "forecast": {"list": []}}
            raise
        return {"current": current, "forecast": forecast}

    def _request_with_retries(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError(f"OpenWeather response from {url} is not a JSON object")
                return data
            except requests.HTTPError as exc:
                status = self._status_code(exc)
                detail = self._http_error_detail(exc)
                if self.skip_on_auth_failure:
                    if status in (401, 403):
                        raise OpenWeatherAuthError(status, detail) from exc
                last_exc = exc
            except Exception as exc:  # pragma: no cover - network failure
                last_exc = exc
            time.sleep(self.backoff * attempt)
        if last_exc:
            raise RuntimeError(f"OpenWeather request failed after {self.retries} attempts for {url}: {last_exc}") from last_exc
        raise RuntimeError(f"OpenWeather request failed for {url}")

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
