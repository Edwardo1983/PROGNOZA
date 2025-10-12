"""Rainviewer radar nowcast proxy provider."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import requests

from ..core import ForecastFrame, Provider, ensure_schema, resample_frame
from ..normalize import empty_frame, normalize_rainviewer


class RainviewerNowcastProvider(Provider):
    API_ENDPOINT = "https://api.rainviewer.com/public/weather-maps.json"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        ttl: int = 600,
        priority: int = 150,
        cache=None,
        session: Optional[requests.Session] = None,
        base_url: Optional[str] = None,
        retries: int = 2,
        backoff: float = 1.0,
    ) -> None:
        super().__init__(
            "rainviewer_nowcast",
            priority=priority,
            cache=cache,
            ttl=ttl,
            ttl_scopes={"nowcast": ttl},
            session=session,
        )
        self.api_key = api_key or os.getenv("RAINVIEWER_API_KEY")
        self.session = session or requests.Session()
        self.base_url = base_url or self.API_ENDPOINT
        self.retries = retries
        self.backoff = backoff

    def get_hourly(self, start: datetime, end: datetime) -> ForecastFrame:
        return ForecastFrame(empty_frame(), {"source": self.name, "stub": True})

    def supports_nowcast(self) -> bool:
        return True

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        horizon = pd.Timestamp.utcnow().tz_localize("UTC") + pd.Timedelta(hours=next_hours)

        def _fetch() -> pd.DataFrame:
            if not self.api_key:
                return empty_frame()
            payload = self._request()
            frame = normalize_rainviewer(payload)
            if frame.empty:
                return frame
            return frame.loc[frame.index <= horizon]

        frame = self.fetch_with_cache(
            "nowcast",
            {"horizon": next_hours},
            _fetch,
            ttl=self.ttl_for("nowcast", fallback=600),
        )
        frame = ensure_schema(frame)
        if frame.empty:
            return ForecastFrame(frame, {"source": self.name, "stub": True})
        resampled = resample_frame(frame, "15min", method="pad", limit=1)
        return ForecastFrame(resampled, {"source": self.name})

    def _request(self) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(self.base_url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # pragma: no cover - network failure
                last_exc = exc
                time.sleep(self.backoff * attempt)
        raise RuntimeError(f"Rainviewer request failed after {self.retries} attempts: {last_exc}")
