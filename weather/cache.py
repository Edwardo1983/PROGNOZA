"""Simple SQLite-based cache for provider responses."""
from __future__ import annotations

import io
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_CACHE_PATH = Path(".cache") / "weather_cache.sqlite"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS weather_cache (
    provider TEXT NOT NULL,
    scope TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    expires_at REAL NOT NULL,
    payload BLOB NOT NULL,
    PRIMARY KEY (provider, scope, cache_key)
);
"""


class WeatherCache:
    """A tiny sqlite cache storing DataFrames as pickle blobs."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path = Path(path) if path else DEFAULT_CACHE_PATH
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    @classmethod
    def default(cls) -> "WeatherCache":
        return cls(DEFAULT_CACHE_PATH)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def get(self, provider: str, scope: str, cache_key: str) -> Optional[pd.DataFrame]:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "SELECT expires_at, payload FROM weather_cache WHERE provider=? AND scope=? AND cache_key=?",
                (provider, scope, cache_key),
            )
            row = cursor.fetchone()
            if not row:
                return None
            expires_at, payload = row
            if expires_at < time.time():
                conn.execute(
                    "DELETE FROM weather_cache WHERE provider=? AND scope=? AND cache_key=?",
                    (provider, scope, cache_key),
                )
                conn.commit()
                return None
        buffer = io.BytesIO(payload)
        buffer.seek(0)
        return pd.read_pickle(buffer)

    def set(
        self,
        provider: str,
        scope: str,
        cache_key: str,
        frame: pd.DataFrame,
        ttl_seconds: int,
    ) -> None:
        expires_at = time.time() + ttl_seconds
        payload = io.BytesIO()
        frame.to_pickle(payload, compression=None)
        with self._lock, self._connect() as conn:
            conn.execute(
                "REPLACE INTO weather_cache (provider, scope, cache_key, expires_at, payload) VALUES (?, ?, ?, ?, ?)",
                (provider, scope, cache_key, expires_at, payload.getvalue()),
            )
            conn.commit()
