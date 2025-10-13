"""Core module tests covering scheduling and data quality."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for core module")


def test_poll_loop_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the polling loop aligns to minute boundaries with a fake clock."""
    from app import poll

    logger.info("Running poll loop alignment test")

    current = {"wall": 100.0, "mono": 50.0}
    scheduled_calls: list[float | None] = []

    def fake_time() -> float:
        return current["wall"]

    def fake_monotonic() -> float:
        return current["mono"]

    def fake_sleep(seconds: float) -> None:
        current["wall"] += seconds
        current["mono"] += seconds

    def fake_poll_once(*, scheduled_wall_time: float | None = None, **_: object) -> dict[str, object]:
        scheduled_calls.append(scheduled_wall_time)
        payload = {
            "start_delay_s": 0.0,
            "started_at": current["wall"],
            "scheduled_start": scheduled_wall_time,
        }
        current["wall"] += 0.5
        current["mono"] += 0.5
        return payload

    monkeypatch.setattr(poll.time, "time", fake_time)
    monkeypatch.setattr(poll.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(poll.time, "sleep", fake_sleep)
    monkeypatch.setattr(poll, "poll_once", fake_poll_once)
    monkeypatch.setattr("builtins.print", lambda *_, **__: None)

    poll.poll_loop(interval_s=60, cycles=3, sync=True)

    assert scheduled_calls == [120.0, 180.0, 240.0]


def test_data_quality_validation_and_repair(tmp_path: Path) -> None:
    """Validate and repair a tiny CSV ensuring gaps are filled deterministically."""
    from core.data_quality import auto_repair_csv, validate_csv

    logger.info("Running data quality validation test")

    index = pd.date_range("2024-01-01T00:00:00Z", periods=5, freq="1min")
    frame = pd.DataFrame(
        {
            "timestamp": index.astype(str),
            "power_active_total": [10, 11, 12, 13, 14],
            "power_reactive_total": [1, 1, 1, 1, 1],
        }
    )
    full_csv = tmp_path / "umg" / "full.csv"
    full_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(full_csv, index=False)

    cfg = {"timezone": "UTC", "drift_sec_max": 3, "ranges": {}, "forward_fill_max": 2}
    result = validate_csv(full_csv, cfg)
    assert result["ok"] is True
    assert result["stats"]["missing_rate"] == pytest.approx(0.0, abs=1e-6)

    gapped = frame.drop(2).reset_index(drop=True)
    csv_path = tmp_path / "umg" / "sample.csv"
    gapped.to_csv(csv_path, index=False)

    repair_out = tmp_path / "umg" / "repaired.csv"
    repaired = auto_repair_csv(csv_path, repair_out, cfg)
    generated = repaired["repair"]["generated_rows"]
    assert generated >= 1
    repaired_frame = pd.read_csv(repair_out)
    assert len(repaired_frame) >= len(frame)


def test_vpn_connection_context(mock_vpn: Path) -> None:
    """Exercise VPN connect/disconnect flows using the fake manager."""
    from app.vpn_connection import VPNConnection

    logger.info("Running VPN connection happy-path test")

    vpn = VPNConnection()
    status = vpn.connect()
    assert status["is_connected"] is True
    vpn.disconnect()
    final_status = vpn.status()
    assert final_status["is_connected"] is False
