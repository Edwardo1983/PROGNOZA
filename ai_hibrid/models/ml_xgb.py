"""XGBoost regression helpers."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import xgboost as xgb
except ImportError as exc:  # pragma: no cover - handled at runtime if missing
    raise RuntimeError("xgboost must be installed to use ai_hibrid.models.ml_xgb") from exc

from ..metrics.eval import mape, rmse


def default_params() -> Dict[str, object]:
    return {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 3,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "n_jobs": 1,
        "random_state": 42,
    }


def train_xgb(
    features: pd.DataFrame,
    target: pd.Series,
    params: Optional[Dict[str, object]] = None,
    validation_fraction: float = 0.2,
) -> Tuple[xgb.XGBRegressor, Dict[str, float]]:
    """Train an XGBoost regressor with a simple chronological split."""
    if len(features) != len(target):
        raise ValueError("features and target must have the same length")
    if len(features) < 10:
        raise ValueError("At least 10 samples are required to train the model")

    params = {**default_params(), **(params or {})}

    split_idx = max(1, int(len(features) * (1 - validation_fraction)))
    X_train = features.iloc[:split_idx]
    y_train = target.iloc[:split_idx]
    X_valid = features.iloc[split_idx:]
    y_valid = target.iloc[split_idx:]

    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)

    if not y_valid.empty:
        preds = model.predict(X_valid)
        metrics = {
            "mape": float(mape(y_valid, preds)),
            "rmse": float(rmse(y_valid, preds)),
        }
    else:
        metrics = {"mape": float("nan"), "rmse": float("nan")}
    return model, metrics


def predict_xgb(model: xgb.XGBRegressor, features: pd.DataFrame) -> np.ndarray:
    return model.predict(features)
