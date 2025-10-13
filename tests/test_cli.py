"""CLI smoke tests using Typer's runner with extensive mocking."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd
from typer.testing import CliRunner

from tests.conftest import get_test_logger
from tests.helpers import FakeVpnConnection

logger = get_test_logger(__name__)
logger.info("Starting tests for CLI module")


def _prepare_runner() -> CliRunner:
    runner = CliRunner()
    return runner


def test_cli_help(monkeypatch) -> None:
    """Base --help command renders without prompting for language."""
    from cli import app as cli_app

    logger.info("Running CLI --help test")
    monkeypatch.setattr(cli_app, "configure_logging", lambda *_: None)

    runner = _prepare_runner()
    with runner.isolated_filesystem():
        Path(".progonzarc").write_text("lang=en", encoding="utf-8")
        result = runner.invoke(cli_app.app, ["--help"])
    assert result.exit_code == 0
    assert "PROGONZA" in result.stdout


def test_vpn_commands(monkeypatch) -> None:
    """Exercise vpn status/connect/disconnect commands using fake VPN."""
    from cli import app as cli_app
    from cli.subapps import vpn as vpn_cli

    logger.info("Running CLI VPN command tests")

    monkeypatch.setattr(cli_app, "configure_logging", lambda *_: None)
    monkeypatch.setattr(vpn_cli, "VPNConnection", FakeVpnConnection)
    monkeypatch.setattr(vpn_cli, "_check_tcp", lambda *_: True)

    runner = _prepare_runner()
    with runner.isolated_filesystem():
        Path(".progonzarc").write_text("lang=en", encoding="utf-8")
        status = runner.invoke(cli_app.app, ["vpn", "status"])
        connect = runner.invoke(cli_app.app, ["vpn", "connect"])
        disconnect = runner.invoke(cli_app.app, ["vpn", "disconnect"])

    assert status.exit_code == 0 and "is_connected" in status.stdout
    assert connect.exit_code == 0 and "vpn_ip" in connect.stdout
    assert disconnect.exit_code == 0


def test_system_vpn_weather(monkeypatch) -> None:
    """system vpn-weather completes quickly with mocked scheduler and router."""
    from cli import app as cli_app
    from cli.subapps import system as system_cli

    logger.info("Running system vpn-weather test")

    call_log: List[float | None] = []

    monkeypatch.setattr(cli_app, "configure_logging", lambda *_: None)

    class DummyRouter:
        def __init__(self) -> None:
            self.nowcast_calls = 0
            self.hourly_calls = 0

        def get_nowcast(self, hours: int):
            self.nowcast_calls += 1
            idx = pd.date_range("2024-01-01T00:00:00Z", periods=hours * 4, freq="15min", tz="UTC")
            return pd.DataFrame({"temp_C": range(len(idx))}, index=idx)

        def get_hourly(self, start, end):
            self.hourly_calls += 1
            idx = pd.date_range(start, end, freq="1h", tz="UTC")
            return pd.DataFrame({"temp_C": range(len(idx))}, index=idx)

    router = DummyRouter()

    monkeypatch.setattr(system_cli, "_build_router", lambda *_: router)
    monkeypatch.setattr(system_cli, "_persist_weather", lambda *_, **__: None)

    current = {"value": 0.0}

    def fake_time() -> float:
        current["value"] += 1.0
        return current["value"]

    def fake_sleep(seconds: float) -> None:
        current["value"] += seconds

    def fake_sleep_until(target: float) -> None:
        current["value"] = max(current["value"], target)

    monkeypatch.setattr(system_cli.time, "time", fake_time)
    monkeypatch.setattr(system_cli.time, "sleep", fake_sleep)
    monkeypatch.setattr(system_cli, "_sleep_until", fake_sleep_until)

    def fake_poll_once(*, scheduled_wall_time=None, **_):
        call_log.append(scheduled_wall_time)
        return {"start_delay_s": 0.0}

    monkeypatch.setattr(system_cli, "poll_once", fake_poll_once)

    runner = _prepare_runner()
    with runner.isolated_filesystem():
        Path(".progonzarc").write_text("lang=en", encoding="utf-8")
        result = runner.invoke(
            cli_app.app,
            ["system", "vpn-weather", "--duration", "5"],
        )

    assert result.exit_code == 0
    assert call_log, "poll_once should be invoked at least once"
    assert "Scenariul" in result.stdout


def test_ui_start_command(monkeypatch, mock_uvicorn) -> None:
    """UI start subcommand delegates to the patched uvicorn entrypoint."""
    from cli import app as cli_app

    logger.info("Running CLI UI start test")

    monkeypatch.setattr(cli_app, "configure_logging", lambda *_: None)

    runner = _prepare_runner()
    with runner.isolated_filesystem():
        Path(".progonzarc").write_text("lang=en", encoding="utf-8")
        result = runner.invoke(cli_app.app, ["ui", "start", "--open"])

    assert result.exit_code == 0
    assert mock_uvicorn["start"] == ("127.0.0.1", 8090, True)
