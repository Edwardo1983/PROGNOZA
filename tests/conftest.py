"""Shared pytest configuration and fixtures for PROGNOZA."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Generator, Iterable, Tuple

import pandas as pd
import pytest

from tests.helpers import (
    FakeHttpResponse,
    FakeModbusClient,
    FakeOpenVPNManager,
    FakeProvider,
    build_fake_umg_frame,
    build_fake_weather_frame,
    ensure_directory,
    write_csv,
    write_parquet,
)

LOGS_ROOT = Path(__file__).resolve().parents[1] / "logs" / "tests"
SESSION_LOG = LOGS_ROOT / "pytest.session.log"
_MODULE_HANDLERS: Dict[str, logging.Handler] = {}


def _initialise_logging() -> None:
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    (LOGS_ROOT / ".gitkeep").touch(exist_ok=True)

    handler = logging.FileHandler(SESSION_LOG, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)


def get_test_logger(module_name: str) -> logging.Logger:
    """Return a logger writing into ``logs/tests/<module>.log``."""
    normalised = module_name.replace("tests.", "")
    logger = logging.getLogger(f"tests.{normalised}")
    logger.setLevel(logging.INFO)
    if normalised not in _MODULE_HANDLERS:
        log_path = LOGS_ROOT / f"{normalised}.log"
        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        _MODULE_HANDLERS[normalised] = handler
    return logger


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:  # noqa: D401 - pytest hook
    _initialise_logging()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterable[pytest.TestReport]:
    outcome = yield
    report = outcome.get_result()
    if report.outcome != "failed":
        return
    module = getattr(item, "module", None)
    module_name = getattr(module, "__name__", "tests")
    target = LOGS_ROOT / f"{module_name.split('.')[-1]}.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write("\n=== TEST FAILURE ===\n")
        handle.write(f"nodeid: {item.nodeid}\n")
        handle.write(f"phase: {report.when}\n")
        handle.write(str(report.longrepr))
        handle.write("\n")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def logs_dir() -> Path:
    _initialise_logging()
    return LOGS_ROOT


@pytest.fixture
def fake_umg_csv(tmp_path: Path) -> Path:
    frame = build_fake_umg_frame()
    path = tmp_path / "umg" / "measurements_20240101.csv"
    return write_csv(frame, path)


@pytest.fixture
def fake_weather_parquet(tmp_path: Path) -> Path:
    frame = build_fake_weather_frame()
    path = tmp_path / "weather" / "weather_hourly.parquet"
    return write_parquet(frame, path)


@pytest.fixture
def mock_vpn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    from app import vpn_connection

    assets_dir = tmp_path / "assets"
    profile_path = tmp_path / "profile.ovpn"
    profile_path.write_text("client\n", encoding="utf-8")

    monkeypatch.setattr(vpn_connection.settings, "OVPN_ASSETS_DIR", assets_dir)
    monkeypatch.setattr(vpn_connection.settings, "LOG_FILE", tmp_path / "vpn.log")
    monkeypatch.setattr(vpn_connection.settings, "OVPN_INPUT", profile_path)
    monkeypatch.setattr(vpn_connection.settings, "PROFILE_NAME", "pytest-profile")
    monkeypatch.setattr(vpn_connection.settings, "CONNECT_TIMEOUT_S", 5)
    monkeypatch.setattr(vpn_connection.settings, "UMG_IP", "192.168.50.10")
    monkeypatch.setattr(vpn_connection.settings, "UMG_TCP_PORT", 502)

    monkeypatch.setattr(vpn_connection, "OpenVPNManager", FakeOpenVPNManager)
    monkeypatch.setattr(
        vpn_connection.ovpn_config,
        "parse_ovpn_file",
        lambda path: {"text": "client\n"},
    )
    monkeypatch.setattr(
        vpn_connection.ovpn_config,
        "generate_clean_config",
        lambda *args, **kwargs: "client\n",
    )

    def _write(clean_text: str, assets_dir: Path, profile_name: str) -> Path:
        assets_dir.mkdir(parents=True, exist_ok=True)
        out = assets_dir / f"{profile_name}.ovpn"
        out.write_text(clean_text, encoding="utf-8")
        return out

    monkeypatch.setattr(vpn_connection.ovpn_config, "write_clean_files", _write)
    monkeypatch.setattr(vpn_connection.VPNConnection, "_wait_for_ip", lambda self, timeout_s: "10.8.0.2")
    monkeypatch.setattr(
        vpn_connection.VPNConnection,
        "_test_umg_connectivity",
        lambda self, timeout_s, min_attempts: (True, True, True),
    )
    monkeypatch.setattr(vpn_connection.VPNConnection, "_get_vpn_ip", lambda self: "10.8.0.2")
    return tmp_path


@pytest.fixture
def mock_modbus(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import janitza_client

    monkeypatch.setattr(janitza_client, "ModbusTcpClient", FakeModbusClient)
    monkeypatch.setattr(janitza_client.JanitzaUMG, "tcp_ping", staticmethod(lambda *_, **__: 12.5))
    monkeypatch.setattr(
        janitza_client.JanitzaUMG,
        "_read_batch",
        lambda self, client, start, count: [round(0.1 * idx, 3) for idx in range(count)],
    )
    monkeypatch.setattr(
        janitza_client.JanitzaUMG,
        "_read_float",
        lambda self, client, address: round((address % 100) / 10.0, 3),
    )


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    import requests

    payload = {
        "hourly": {
            "time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "temperature_2m": [5.0, 6.0],
            "windspeed_10m": [3.2, 3.4],
            "winddirection_10m": [180, 200],
            "cloudcover": [20, 30],
            "relativehumidity_2m": [60, 62],
            "surface_solar_radiation_downward": [100.0, 120.0],
        }
    }

    def _fake_get(*args, **kwargs):
        return FakeHttpResponse(payload)

    class _Session:
        def get(self, *args, **kwargs):
            return _fake_get(*args, **kwargs)

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "Session", lambda: _Session())
    return payload


@pytest.fixture
def mock_uvicorn(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Tuple[str, int, bool]]:
    calls: Dict[str, Tuple[str, int, bool]] = {}

    def _fake_start(host: str, port: int, *, open_browser: bool = True) -> None:
        calls["start"] = (host, port, open_browser)

    monkeypatch.setattr("ui.server.start_ui", _fake_start)
    return calls


@pytest.fixture(scope="session")
def weather_cache_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("weather-cache") / "cache.sqlite"


@pytest.fixture(autouse=True)
def patch_weather_cache(monkeypatch: pytest.MonkeyPatch, weather_cache_dir: Path) -> None:
    from weather import cache as weather_cache

    def _factory(path: Path | None = None) -> weather_cache.WeatherCache:
        target = path or weather_cache_dir
        return weather_cache.WeatherCache(path=target)

    monkeypatch.setattr(weather_cache.WeatherCache, "default", classmethod(lambda cls: _factory()))


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TOMORROW_IO_API_KEY", "TOMORROWIO_API_KEY"):
        monkeypatch.delenv(key, raising=False)


__all__ = [
    "get_test_logger",
]
