"""Mock implementations used by the pytest suite."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

import pandas as pd

from weather.core import ForecastFrame, Provider

__all__ = [
    "FakeHttpResponse",
    "FakeModbusClient",
    "FakeOpenVPNManager",
    "FakeProvider",
    "FakeVpnConnection",
]


class FakeHttpResponse:
    """Minimal response object for mocked HTTP calls."""

    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self) -> Dict[str, Any]:
        return self._payload


class FakeModbusClient:
    """In-memory Modbus client returning deterministic float values."""

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connected = False

    def connect(self) -> bool:  # pragma: no cover - trivial
        self.connected = True
        return True

    def close(self) -> None:  # pragma: no cover - trivial
        self.connected = False

    @staticmethod
    def _float_from_address(address: int) -> float:
        return round((address % 1000) / 10.0, 3)

    def read_holding_registers(self, address: int, count: int, slave: int) -> SimpleNamespace:
        registers = []
        for offset in range(count * 2):
            base = self._float_from_address(address + offset)
            registers.append(int(base * 100))
        return SimpleNamespace(isError=lambda: False, registers=registers)


class FakeOpenVPNManager:
    """Fake manager that records lifecycle calls for assertions."""

    def __init__(self, logger: Any) -> None:
        self.logger = logger
        self.profile_running = False
        self.pid = 4242

    def prepare_profile(self, clean_profile: Any, assets_dir: Any, profile_name: str) -> str:
        return f"{assets_dir}/{profile_name}.ovpn"

    def start(self, profile_name: str) -> Dict[str, Any]:
        self.profile_running = True
        return {"pid": self.pid}

    def disconnect(self, profile_name: str) -> None:
        self.profile_running = False

    def stop_all(self) -> None:
        self.profile_running = False

    def get_profile_pid(self, profile_name: str) -> Optional[int]:
        return self.pid if self.profile_running else None


class _MemoryCache:
    def __init__(self) -> None:
        self._storage: Dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}

    def get(self, provider: str, scope: str, cache_key: str) -> Optional[pd.DataFrame]:
        key = (provider, scope, cache_key)
        payload = self._storage.get(key)
        if not payload:
            return None
        expires_at, frame = payload
        if expires_at < time.time():
            self._storage.pop(key, None)
            return None
        return frame.copy()

    def set(
        self,
        provider: str,
        scope: str,
        cache_key: str,
        frame: pd.DataFrame,
        ttl_seconds: int,
    ) -> None:
        self._storage[(provider, scope, cache_key)] = (time.time() + ttl_seconds, frame.copy())


@dataclass
class FakeProvider(Provider):
    """Deterministic provider used to exercise :class:`WeatherRouter`."""

    name: str
    priority: int = 10
    hourly_builder: Callable[[pd.Timestamp, pd.Timestamp], pd.DataFrame] = field(
        default=lambda start, end: pd.DataFrame()
    )
    nowcast_builder: Optional[Callable[[int], pd.DataFrame]] = None

    def __post_init__(self) -> None:  # pragma: no cover - dataclass init
        super().__init__(self.name, priority=self.priority, cache=_MemoryCache(), ttl=300)

    def get_hourly(self, start: Any, end: Any) -> ForecastFrame:
        start_ts = pd.Timestamp(start)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        else:
            start_ts = start_ts.tz_convert("UTC")

        end_ts = pd.Timestamp(end)
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")

        def _builder() -> pd.DataFrame:
            frame = self.hourly_builder(start_ts, end_ts)
            frame.index = pd.to_datetime(frame.index, utc=True)
            return frame

        frame = self.fetch_with_cache(
            "hourly",
            {"start": start_ts.isoformat(), "end": end_ts.isoformat()},
            _builder,
            ttl=60,
        )
        return ForecastFrame(frame, {"source": self.name})

    def supports_nowcast(self) -> bool:
        return self.nowcast_builder is not None

    def get_nowcast(self, next_hours: int = 2) -> ForecastFrame:
        if not self.nowcast_builder:
            raise RuntimeError("Nowcast not available")
        def _builder() -> pd.DataFrame:
            frame = self.nowcast_builder(next_hours)
            frame.index = pd.to_datetime(frame.index, utc=True)
            return frame

        frame = self.fetch_with_cache(
            "nowcast",
            {"horizon": int(next_hours)},
            _builder,
            ttl=15,
        )
        return ForecastFrame(frame, {"source": self.name})


class FakeVpnConnection:
    """Simplified VPN connection used for CLI simulations."""

    def __init__(self) -> None:
        self.connected = False
        self.history: list[str] = []

    def connect(self) -> Dict[str, Any]:
        self.connected = True
        self.history.append("connect")
        return {"is_connected": True, "vpn_ip": "10.8.0.2", "umg_ok": True}

    def disconnect(self) -> None:
        self.connected = False
        self.history.append("disconnect")

    def status(self) -> Dict[str, Any]:
        self.history.append("status")
        return {"is_connected": self.connected, "vpn_ip": "10.8.0.2", "umg_ok": self.connected}
