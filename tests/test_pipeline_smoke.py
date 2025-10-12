from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ai_hibrid.pipeline.predict import predict_pipeline
from ai_hibrid.pipeline.train import train_pipeline


def _build_synthetic_weather(index: pd.DatetimeIndex) -> pd.DataFrame:
    hours = (index.hour + index.minute / 60).values
    ghi = np.clip(800 * np.sin((hours / 24) * np.pi), 0, None)
    return pd.DataFrame(
        {
            "temp_C": 20 + 5 * np.sin((hours / 24) * 2 * np.pi),
            "wind_ms": 2 + 0.5 * np.cos((hours / 24) * 2 * np.pi),
            "wind_deg": 180,
            "clouds_pct": 20,
            "humidity": 55,
            "ghi_Wm2": ghi,
            "uvi": ghi / 100.0,
        },
        index=index,
    )


def _write_config(path: Path) -> None:
    content = """site:
  latitude: 44.4
  longitude: 26.1
  timezone: "Europe/Bucharest"
system:
  kWp: 1.5
  tilt: 30
  azimuth: 180
  gamma_Pmp: -0.004
  bos_loss: 0.05
temperature_model:
  c1: 0.02
  c2: -0.5
training:
  validation_fraction: 0.2
"""
    path.write_text(content, encoding="utf-8")


def test_pipeline_end_to_end(tmp_path: Path) -> None:
    index = pd.date_range("2024-01-01 06:00", periods=72, freq="h", tz="UTC")
    weather = _build_synthetic_weather(index)
    weather_path = tmp_path / "weather.csv"
    weather.reset_index().to_csv(weather_path, index=False)

    physics_power = 1500 * (weather["ghi_Wm2"] / 1000.0)
    noise = np.random.default_rng(42).normal(0, 50, size=len(physics_power))
    measurements = pd.DataFrame({"timestamp": index, "power_W": (physics_power + noise).clip(lower=0)})
    meas_path = tmp_path / "measurements.csv"
    measurements.to_csv(meas_path, index=False)

    cfg_path = tmp_path / "hybrid.yaml"
    _write_config(cfg_path)

    artifact_root = tmp_path / "artifacts"
    train_metrics = train_pipeline(
        str(meas_path),
        str(weather_path),
        str(cfg_path),
        artifact_root=artifact_root,
    )
    assert "physics" in train_metrics

    forecast_out = tmp_path / "forecast.csv"
    actuals_path = tmp_path / "actuals.csv"
    measurements.to_csv(actuals_path, index=False)

    metrics = predict_pipeline(
        str(weather_path),
        str(cfg_path),
        horizon=24,
        out_path=forecast_out,
        actuals_path=str(actuals_path),
        artifact_root=artifact_root,
    )

    assert forecast_out.exists()
    assert metrics
