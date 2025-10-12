"""Common evaluation metrics for PV forecasting."""
from __future__ import annotations

from typing import Dict, Iterable

import numpy as np
import pandas as pd


def _to_numpy(values) -> np.ndarray:
    if isinstance(values, (pd.Series, pd.Index)):
        return values.to_numpy(dtype=float)
    return np.asarray(values, dtype=float)


def mape(y_true, y_pred, epsilon: float = 1e-3) -> float:
    y_true = _to_numpy(y_true)
    y_pred = _to_numpy(y_pred)
    denominator = np.clip(np.abs(y_true), epsilon, None)
    return float(np.mean(np.abs((y_true - y_pred) / denominator)))


def rmse(y_true, y_pred) -> float:
    y_true = _to_numpy(y_true)
    y_pred = _to_numpy(y_pred)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def pinball_loss(y_true, y_pred, quantile: float) -> float:
    y_true = _to_numpy(y_true)
    y_pred = _to_numpy(y_pred)
    diff = y_true - y_pred
    return float(np.mean(np.maximum(quantile * diff, (quantile - 1) * diff)))


def evaluate_metrics(
    y_true,
    y_pred,
    *,
    quantiles: Iterable[float] | None = None,
) -> Dict[str, float]:
    metrics = {
        "mape": mape(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
    }
    if quantiles:
        for q in quantiles:
            metrics[f"pinball_{q:.2f}"] = pinball_loss(y_true, y_pred, q)
    return metrics
