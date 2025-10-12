"""Training entry-point for the hybrid PV forecasting pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from joblib import dump

from ..metrics.eval import evaluate_metrics
from ..models.blender import blend_predictions, tune_alpha
from ..models.ml_xgb import predict_xgb, train_xgb
from .dataset import build_training_dataset
from .utils import ensure_directory, load_config, save_json

DEFAULT_ARTIFACT_ROOT = Path(__file__).resolve().parents[1] / "models" / "artifacts"


def _artifact_paths(artifact_root: Path | None = None) -> Dict[str, Path]:
    root = Path(artifact_root) if artifact_root else DEFAULT_ARTIFACT_ROOT
    return {
        "root": root,
        "model": root / "xgb.pkl",
        "blend": root / "blend_params.json",
        "metrics": root / "train_metrics.json",
    }


def train_pipeline(
    measurement_path: str,
    weather_path: str,
    cfg_path: str | Path,
    *,
    validation_fraction: float = 0.2,
    artifact_root: Path | None = None,
) -> Dict[str, Dict[str, float]]:
    config = load_config(cfg_path)
    dataset, _ = build_training_dataset(measurement_path, weather_path, config)

    target = dataset["target_power_W"]
    feature_cols = [col for col in dataset.columns if col != "target_power_W"]
    features = dataset[feature_cols]

    paths = _artifact_paths(artifact_root)
    model_path = paths["model"]
    blend_path = paths["blend"]
    metrics_path = paths["metrics"]

    model, ml_metrics = train_xgb(features, target, validation_fraction=validation_fraction)
    ensure_directory(model_path)
    dump(model, model_path)

    split_idx = max(1, int(len(dataset) * (1 - validation_fraction)))
    X_valid = features.iloc[split_idx:]
    y_valid = target.iloc[split_idx:]
    physics_valid = dataset["power_physics_W"].iloc[split_idx:]

    ml_valid = pd.Series(predict_xgb(model, X_valid), index=X_valid.index)
    alpha, blend_mape = tune_alpha(physics_valid, ml_valid, y_valid)
    blended_valid = blend_predictions(physics_valid, ml_valid, alpha)

    ensure_directory(blend_path)
    save_json({"alpha": alpha}, blend_path)

    metrics = {
        "physics": evaluate_metrics(y_valid, physics_valid),
        "ml": evaluate_metrics(y_valid, ml_valid),
        "blended": evaluate_metrics(y_valid, blended_valid),
        "training": {"mape": ml_metrics.get("mape"), "rmse": ml_metrics.get("rmse")},
    }
    ensure_directory(metrics_path)
    save_json(metrics, metrics_path)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train hybrid PV forecasting pipeline.")
    parser.add_argument("--meas", required=True, help="Path to measurement CSV with timestamp,power_W columns.")
    parser.add_argument("--weather", required=True, help="Path to weather data (CSV/Parquet).")
    parser.add_argument("--cfg", default=str(Path(__file__).resolve().parents[1] / "config" / "hybrid.yaml"))
    parser.add_argument("--validation-fraction", type=float, default=0.2, help="Fraction of data for validation.")
    args = parser.parse_args(argv)

    train_pipeline(args.meas, args.weather, args.cfg, validation_fraction=args.validation_fraction)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
