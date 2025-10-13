"""FastAPI UI smoke-tests covering key endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd
from fastapi.testclient import TestClient

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for UI module")


def _prepare_ui_dirs(
    tmp_path: Path,
    fake_umg_csv: Path,
    fake_weather_parquet: Path,
    monkeypatch,
) -> Dict[str, Path]:
    from ui import data_access

    data_root = tmp_path / "data"
    janitza_dir = data_root / "raw" / "umg509"
    weather_dir = data_root / "weather"
    janitza_dir.mkdir(parents=True, exist_ok=True)
    weather_dir.mkdir(parents=True, exist_ok=True)

    target_csv = janitza_dir / fake_umg_csv.name
    target_csv.write_bytes(Path(fake_umg_csv).read_bytes())

    target_weather = weather_dir / fake_weather_parquet.name
    target_weather.write_bytes(Path(fake_weather_parquet).read_bytes())

    monkeypatch.setattr(data_access, "JANITZA_DIRS", [janitza_dir])
    monkeypatch.setattr(data_access, "WEATHER_DIR", weather_dir)
    monkeypatch.setattr(data_access, "FORECASTS_DIR", weather_dir)
    monkeypatch.setattr(data_access, "RESAMPLE_RULE", "5min")

    return {
        "janitza": janitza_dir,
        "weather": weather_dir,
    }


def test_ui_endpoints(monkeypatch, tmp_path, fake_umg_csv, fake_weather_parquet) -> None:
    """Exercise primary UI routes using synthetic data."""
    from ui import server

    logger.info("Running UI endpoint tests")

    _prepare_ui_dirs(tmp_path, fake_umg_csv, fake_weather_parquet, monkeypatch)
    client = TestClient(server.app)

    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "Janitza" in resp.text

    start = "2024-01-01T00:00:00Z"
    end = "2024-01-01T02:00:00Z"
    metrics = "power_active_total,power_factor"
    resp = client.get("/ui/api/janitza", params={"start": start, "end": end, "metrics": metrics})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["series"], "Expected Janitza series"
    first_series = payload["series"][0]
    assert first_series["data"], "Series should contain datapoints"

    weather_key = Path(fake_weather_parquet).stem.lower()
    resp = client.get(
        "/ui/api/weather",
        params={"type": weather_key, "start": start, "end": end},
    )
    assert resp.status_code == 200
    weather_payload = resp.json()
    assert any(series["name"].startswith("temp") for series in weather_payload["series"])

    resp = client.get(
        "/ui/janitza/table",
        params={"start": start, "end": end, "metrics": "power_active_total,power_factor"},
    )
    assert resp.status_code == 200
    assert "kW" in resp.text or "Power" in resp.text
