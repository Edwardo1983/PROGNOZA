"""Blend deterministic and ML forecasts."""
from __future__ import annotations

from typing import Iterable, Tuple

import numpy as np
import pandas as pd

from ..metrics.eval import mape


def blend_predictions(physics: pd.Series, ml: pd.Series, alpha: float) -> pd.Series:
    """Blend predictions using weight alpha for physics component."""
    alpha = float(np.clip(alpha, 0.0, 1.0))
    return alpha * physics + (1.0 - alpha) * ml


def tune_alpha(
    physics: pd.Series,
    ml: pd.Series,
    actual: pd.Series,
    alphas: Iterable[float] | None = None,
) -> Tuple[float, float]:
    """Return (alpha, score) that minimises MAPE on validation data."""
    if alphas is None:
        alphas = np.linspace(0, 1, num=21)

    best_alpha = 0.5
    best_score = float("inf")
    for candidate in alphas:
        blended = blend_predictions(physics, ml, candidate)
        score = mape(actual, blended)
        if np.isnan(score):
            continue
        if score < best_score:
            best_score = score
            best_alpha = float(candidate)
    return best_alpha, float(best_score)
