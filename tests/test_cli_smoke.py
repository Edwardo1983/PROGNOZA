from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

try:
    from typer.testing import CliRunner
except ImportError:  # pragma: no cover
    pytest.skip("Typer not installed", allow_module_level=True)

from cli import i18n
from cli import app as cli_app

runner = CliRunner() if 'CliRunner' in globals() else None


@pytest.fixture(autouse=True)
def reset_lang(tmp_path, monkeypatch):
    rc = tmp_path / ".progonzarc"
    monkeypatch.setattr(i18n, "RC_FILE", rc, raising=False)
    monkeypatch.setattr(i18n, "_LANG", None, raising=False)
    monkeypatch.setattr(i18n, "_CACHE", {}, raising=False)

    original_path = cli_app.Path

    def fake_path(value: str) -> Path:
        if value == ".progonzarc":
            return rc
        return original_path(value)

    monkeypatch.setattr(cli_app, "Path", fake_path, raising=False)
    rc.write_text('{"lang": "en"}', encoding="utf-8")
    yield


def test_cli_root_language_prompt():
    if runner is None:
        pytest.skip("Typer not installed")
    result = runner.invoke(cli_app.app, input="en\n")
    assert result.exit_code == 0
    assert i18n.RC_FILE.exists()
    data = json.loads(i18n.RC_FILE.read_text(encoding="utf-8"))
    assert data["lang"] == "en"


def test_vpn_status_runs(monkeypatch):
    if runner is None:
        pytest.skip("Typer not installed")
    from cli.subapps import vpn

    class DummyVPN:
        def status(self) -> Dict[str, Any]:
            return {"is_connected": True, "vpn_ip": "10.0.0.1"}

        def connect(self):
            return {"is_connected": True}

        def disconnect(self):
            return None

    monkeypatch.setattr(vpn, "VPNConnection", DummyVPN)
    monkeypatch.setattr(vpn, "_check_tcp", lambda host, port: True)

    result = runner.invoke(cli_app.app, ["vpn", "status"])
    assert result.exit_code == 0


def test_system_vpn_weather_short(monkeypatch):
    if runner is None:
        pytest.skip("Typer not installed")
    from cli.subapps import system

    monkeypatch.setattr(system, "poll_once", lambda scheduled_wall_time=None: {})

    class DummyRouter:
        def get_nowcast(self, hours: int):
            return {}

    monkeypatch.setattr(system, "_build_router", lambda cfg=None: DummyRouter())

    result = runner.invoke(
        cli_app.app,
        ["system", "vpn-weather", "--period", "10", "--duration", "1"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
