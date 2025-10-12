"""Dataset preparation for the hybrid PV forecasting pipeline."""
from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd

from ..features.time_feats import build_time_features
from ..features.weather_feats import add_lag_features, prepare_weather_features
from ..features.pv_clear_sky import compute_clearsky_poa
from ..models.physics_baseline import physics_power
from .utils import read_measurements, read_weather


def build_feature_matrix(
    weather: pd.DataFrame,
    target_index: pd.DatetimeIndex,
    config: Dict[str, dict],
    *,
    include_lags: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    site = config.get("site", {})
    latitude = site.get("latitude")
    longitude = site.get("longitude")
    timezone = site.get("timezone", "UTC")

    weather_aligned = weather.reindex(target_index)
    weather_aligned = weather_aligned.apply(pd.to_numeric, errors="coerce")
    weather_aligned = weather_aligned.interpolate(limit_direction="both")
    time_features = build_time_features(target_index, latitude=latitude, longitude=longitude, timezone=timezone)
    weather_features = prepare_weather_features(weather_aligned)
    clearsky = compute_clearsky_poa(target_index, weather_aligned, config)

    features = pd.concat([time_features, weather_features, clearsky], axis=1)

    if include_lags:
        lag_columns = ["poa_clearsky"]
        if "temp_C" in weather_features.columns:
            lag_columns.append("temp_C")
        features = add_lag_features(features, lag_columns, lags=[1, 2])

    physics_series = physics_power(
        poa=clearsky["poa_clearsky"],
        cell_temperature=clearsky["t_cell"],
        config=config,
    )
    features["power_physics_W"] = physics_series

    features = features.fillna(0.0)
    return features, {
        "time": time_features,
        "weather": weather_features,
        "clearsky": clearsky,
        "physics": physics_series,
    }


def build_training_dataset(
    measurement_path: str,
    weather_path: str,
    config: Dict[str, dict],
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    measurements = read_measurements(measurement_path)
    weather = read_weather(weather_path)

    features, extras = build_feature_matrix(weather, measurements.index, config)
    dataset = features.join(measurements["power_W"].rename("target_power_W"), how="inner").dropna()
    return dataset, extras
