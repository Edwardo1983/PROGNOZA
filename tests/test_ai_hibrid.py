"""Tests for the hybrid AI pipeline training and prediction flows."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for AI Hibrid module")


class DummyModel:
    """Serializable placeholder model used in tests."""

    def __init__(self, bias: float) -> None:
        self.bias = bias


def test_train_and_predict_pipeline(
    tmp_path: Path,
    fake_umg_csv: Path,
    fake_weather_parquet: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end smoke test for train/predict pipelines with lightweight mocks."""
    from ai_hibrid.pipeline import predict as predict_module
    from ai_hibrid.pipeline import train as train_module

    logger.info("Running hybrid pipeline train/predict test")

    timestamps = pd.date_range("2024-01-01T00:00:00Z", periods=24, freq="1h", tz="UTC")
    base = np.arange(len(timestamps), dtype=float)
    physics = pd.Series(100 + base, index=timestamps, name="power_physics_W")
    feature = pd.Series(base, index=timestamps, name="feature_a")
    target = physics + 5

    dataset = pd.concat([feature, physics, target.rename("target_power_W")], axis=1)
    features_only = dataset.drop(columns=["target_power_W"])

    config_payload = {"site": {"timezone": "UTC"}}
    monkeypatch.setattr(train_module, "load_config", lambda path: config_payload)
    monkeypatch.setattr(predict_module, "load_config", lambda path: config_payload)
    monkeypatch.setattr(train_module, "build_training_dataset", lambda *_: (dataset.copy(), {}))
    monkeypatch.setattr(
        predict_module,
        "build_feature_matrix",
        lambda weather, index, cfg, include_lags=True: (features_only.copy(), {}),
    )

    def fake_train_xgb(features: pd.DataFrame, target: pd.Series, validation_fraction: float = 0.2):
        model = DummyModel(bias=float(target.mean()))
        metrics = {"mape": 0.1, "rmse": 0.5}
        return model, metrics

    def fake_predict_xgb(model: DummyModel, features: pd.DataFrame):
        return [model.bias + idx * 0.01 for idx in range(len(features))]

    monkeypatch.setattr(train_module, "train_xgb", fake_train_xgb)
    monkeypatch.setattr(train_module, "predict_xgb", fake_predict_xgb)
    monkeypatch.setattr(predict_module, "predict_xgb", fake_predict_xgb)
    monkeypatch.setattr(train_module, "tune_alpha", lambda *_, **__: (0.4, 1.0))
    monkeypatch.setattr(train_module, "blend_predictions", lambda physics, ml, alpha: physics * (1 - alpha) + ml * alpha)
    monkeypatch.setattr(
        predict_module,
        "blend_predictions",
        lambda physics, ml, alpha: physics * (1 - alpha) + ml * alpha,
    )

    artifact_root = tmp_path / "artifacts"
    metrics = train_module.train_pipeline(
        str(fake_umg_csv),
        str(fake_weather_parquet),
        str(tmp_path / "config.yaml"),
        artifact_root=artifact_root,
    )
    assert set(metrics.keys()) >= {"physics", "ml", "blended"}

    forecast_path = tmp_path / "forecast.csv"
    predict_module.predict_pipeline(
        str(fake_weather_parquet),
        str(tmp_path / "config.yaml"),
        horizon=6,
        out_path=forecast_path,
        artifact_root=artifact_root,
    )
    assert forecast_path.exists()
    forecast = pd.read_csv(forecast_path)
    assert {
        "forecast_power_physics_W",
        "forecast_power_ml_W",
        "forecast_power_W",
    }.issubset(forecast.columns)
    assert forecast["forecast_power_W"].notna().all()
