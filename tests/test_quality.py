from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from zoneinfo import ZoneInfo

from core.data_quality import auto_repair_csv, load_config, validate_csv


def _build_sample_csv(path: Path) -> pd.DataFrame:
    tz = ZoneInfo("Europe/Bucharest")
    base = pd.Timestamp("2024-01-01T00:00:02", tz=tz)
    records = []
    thresholds = (5, 10, 15, 30, 60)

    for minute in range(6):
        if minute == 3:
            continue  # create a one-minute gap
        ts = base + pd.Timedelta(minutes=minute)
        if minute == 2:
            ts += pd.Timedelta(seconds=10)  # drift beyond tolerance

        elapsed_minutes = round((ts - base).total_seconds() / 60.0, 2)
        milestones = ";".join(str(t) for t in thresholds if elapsed_minutes >= t)

        row = {
            "timestamp": ts.replace(microsecond=0).isoformat(),
            "voltage_l1": 180.0 if minute == 4 else 230.0,
            "current_a": 100.0 + minute,
            "freq_hz": 50.0,
            "pf": 0.97,
            "thd_pct": 10.0,
            "elapsed_minutes": elapsed_minutes,
            "milestones": milestones,
        }
        records.append(row)

    frame = pd.DataFrame(records)
    frame.to_csv(path, index=False)
    return frame


@pytest.fixture()
def data_quality_config() -> dict:
    return load_config()


def test_validate_flags_gap_and_outlier(tmp_path: Path, data_quality_config: dict) -> None:
    csv_path = tmp_path / "sample.csv"
    _build_sample_csv(csv_path)

    result = validate_csv(csv_path, data_quality_config)

    assert not result["ok"]
    assert any("missing" in issue.lower() for issue in result["issues"])
    assert any("drift" in issue.lower() for issue in result["issues"])
    assert result["stats"]["missing_rate"] > 0
    assert result["stats"]["late_rate"] > 0
    assert result["stats"]["outlier_rate"] > 0


def test_auto_repair_produces_csv_and_reports(tmp_path: Path, data_quality_config: dict) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "repaired.csv"
    _build_sample_csv(input_csv)

    result = auto_repair_csv(input_csv, output_csv, data_quality_config)

    assert output_csv.exists()
    reports = result["reports"]
    assert reports["json"].exists()
    assert reports["html"].exists()

    with reports["json"].open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert pytest.approx(payload["repaired"]["stats"]["missing_rate"], abs=1e-6) == 0
    assert pytest.approx(payload["repaired"]["stats"]["late_rate"], abs=1e-6) == 0

    html_content = reports["html"].read_text(encoding="utf-8")
    assert "Drift Histogram" in html_content
    assert "Minute Coverage" in html_content
    assert "Range Violations" in html_content
