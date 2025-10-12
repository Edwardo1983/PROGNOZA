"""Forecast generation for the hybrid PV pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from joblib import load

from ..metrics.eval import evaluate_metrics
from ..models.blender import blend_predictions
from ..models.ml_xgb import predict_xgb
from .dataset import build_feature_matrix
from .train import _artifact_paths
from .utils import ensure_directory, load_config, read_weather, save_json

DEFAULT_METRICS_QUANTILES = (0.1, 0.5, 0.9)


def _load_alpha(blend_path: Path) -> float:
    if blend_path.exists():
        data = load_config(blend_path)
        return float(data.get("alpha", 0.5))
    return 0.5


def predict_pipeline(
    weather_path: str,
    cfg_path: str | Path,
    *,
    horizon: int,
    out_path: str | Path,
    actuals_path: Optional[str] = None,
    artifact_root: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    config = load_config(cfg_path)
    weather = read_weather(weather_path)
    paths = _artifact_paths(artifact_root)
    model = load(paths["model"])
    alpha = _load_alpha(paths["blend"])

    features, extras = build_feature_matrix(weather, weather.index, config, include_lags=True)
    # Use last `horizon` timestamps
    features = features.tail(horizon)
    physics_series = features["power_physics_W"]
    ml_pred = pd.Series(predict_xgb(model, features), index=features.index, name="forecast_power_ml_W")
    blended = blend_predictions(physics_series, ml_pred, alpha).rename("forecast_power_W")

    forecast_df = pd.concat(
        [
            physics_series.rename("forecast_power_physics_W"),
            ml_pred,
            blended,
        ],
        axis=1,
    )
    forecast_df.index.name = "timestamp"

    out_path = Path(out_path)
    ensure_directory(out_path)
    forecast_df.to_csv(out_path)

    metrics = {}
    if actuals_path:
        actuals_df = pd.read_csv(actuals_path)
        if "timestamp" not in actuals_df.columns or "power_W" not in actuals_df.columns:
            raise ValueError("Actuals file must contain timestamp and power_W columns")
        actuals_df["timestamp"] = pd.to_datetime(actuals_df["timestamp"], utc=True)
        actuals_df = actuals_df.set_index("timestamp").sort_index()
        forecast_reset = forecast_df.reset_index()
        actuals_reset = actuals_df.reset_index()
        merged = forecast_reset.merge(actuals_reset, on="timestamp", how="inner", suffixes=("_forecast", "_actual"))
        if not merged.empty:
            aligned_forecast = merged["forecast_power_W"]
            aligned_actuals = merged["power_W"]
            metrics = {
                "blended": evaluate_metrics(
                    aligned_actuals, aligned_forecast, quantiles=DEFAULT_METRICS_QUANTILES
                )
            }
            metrics["physics"] = evaluate_metrics(
                aligned_actuals, merged["forecast_power_physics_W"]
            )
            metrics["ml"] = evaluate_metrics(
                aligned_actuals, merged["forecast_power_ml_W"]
            )
        elif actuals_path:
            metrics = {"note": "no_overlap_between_actuals_and_forecast"}

    if metrics:
        metrics_path = out_path.with_suffix(".metrics.json")
        save_json(metrics, metrics_path)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate PV power forecasts.")
    parser.add_argument("--weather", required=True, help="Path to weather data (CSV/Parquet).")
    parser.add_argument("--cfg", default=str(Path(__file__).resolve().parents[1] / "config" / "hybrid.yaml"))
    parser.add_argument("--horizon", type=int, default=48, help="Number of hourly steps to forecast.")
    parser.add_argument("--out", required=True, help="Destination CSV path.")
    parser.add_argument("--actuals", help="Optional CSV with timestamp,power_W for evaluation.")
    args = parser.parse_args(argv)

    predict_pipeline(
        args.weather,
        args.cfg,
        horizon=args.horizon,
        out_path=args.out,
        actuals_path=args.actuals,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
