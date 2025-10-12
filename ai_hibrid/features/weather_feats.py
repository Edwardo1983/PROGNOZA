"""Feature engineering helpers for weather data."""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

DEFAULT_COLUMNS = ("temp_C", "wind_ms", "wind_deg", "clouds_pct", "humidity", "ghi_Wm2", "uvi")


def prepare_weather_features(weather: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalise weather data for model consumption."""
    if weather.index.tz is None:
        weather = weather.tz_localize("UTC")
    weather = weather.sort_index()
    working = weather.copy()
    available_cols = [col for col in DEFAULT_COLUMNS if col in working.columns]
    working[available_cols] = working[available_cols].interpolate(limit_direction="both")
    working = working.ffill().bfill()

    features = pd.DataFrame(index=working.index)
    if "temp_C" in working.columns:
        features["temp_C"] = working["temp_C"]
        features["temp_C_norm"] = (working["temp_C"] - 25.0) / 15.0
    if "wind_ms" in working.columns:
        features["wind_ms"] = working["wind_ms"]
        features["wind_ms_norm"] = working["wind_ms"] / 10.0
    if "wind_deg" in working.columns:
        radians = np.deg2rad(working["wind_deg"])
        features["wind_dir_sin"] = np.sin(radians)
        features["wind_dir_cos"] = np.cos(radians)
    if "clouds_pct" in working.columns:
        features["clouds_pct"] = working["clouds_pct"] / 100.0
    if "humidity" in working.columns:
        features["humidity"] = working["humidity"] / 100.0
    if "ghi_Wm2" in working.columns:
        features["ghi_norm"] = working["ghi_Wm2"] / 1000.0
    if "uvi" in working.columns:
        features["uvi_norm"] = working["uvi"] / 10.0

    return features


def add_lag_features(df: pd.DataFrame, columns: Sequence[str], lags: Iterable[int]) -> pd.DataFrame:
    """Return a new dataframe with lagged versions of columns."""
    augmented = df.copy()
    for col in columns:
        if col not in augmented.columns:
            continue
        for lag in lags:
            augmented[f"{col}_lag_{lag}"] = augmented[col].shift(lag)
    return augmented
