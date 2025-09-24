"""Engine de prognoza D+1 pentru parc fotovoltaic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

import pandas as pd

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("scikit-learn is required for the forecast engine") from exc

from prognoza.config.settings import WeatherConfig


@dataclass(slots=True)
class ForecastResult:
    delivery_day: datetime
    horizon: int
    forecast: pd.Series
    model_error_mae: Optional[float]


class ForecastEngine:
    """Genereaza prognoza D+1 folosind istoric productie si date meteo."""

    def __init__(self, weather: WeatherConfig, n_estimators: int = 200) -> None:
        self._weather = weather
        self._model = RandomForestRegressor(n_estimators=n_estimators, random_state=42)
        self._is_trained = False
        self._latest_mae: Optional[float] = None
        self._feature_columns: Optional[list[str]] = None

    def fit(self, historical: pd.DataFrame, weather_features: pd.DataFrame) -> None:
        dataset = self._build_training_dataset(historical, weather_features)
        if dataset.empty:
            raise ValueError("Insufficient data to train forecast model")
        X = dataset.drop(columns=["target"])
        y = dataset["target"]
        self._model.fit(X, y)
        self._is_trained = True
        self._feature_columns = list(X.columns)
        predictions = self._model.predict(X)
        self._latest_mae = mean_absolute_error(y, predictions)

    def forecast(
        self,
        delivery_day: datetime,
        weather_forecast: pd.DataFrame,
        reference_profile: pd.Series,
    ) -> ForecastResult:
        if not self._is_trained or not self._feature_columns:
            raise RuntimeError("Forecast model not trained")
        features = self._build_forecast_features(weather_forecast, reference_profile)
        missing = [col for col in self._feature_columns if col not in features.columns]
        if missing:
            raise ValueError(f"Missing forecast features: {missing}")
        features = features[self._feature_columns]
        forecast_values = self._model.predict(features)
        index = weather_forecast.index
        if index.tz is None:
            index = index.tz_localize(self._weather.timezone if hasattr(self._weather, "timezone") else "Europe/Bucharest")
        return ForecastResult(
            delivery_day=delivery_day,
            horizon=len(forecast_values),
            forecast=pd.Series(forecast_values, index=index, name="planned_mw"),
            model_error_mae=self._latest_mae,
        )

    def _build_training_dataset(self, historical: pd.DataFrame, weather_features: pd.DataFrame) -> pd.DataFrame:
        merged = historical.join(weather_features, how="inner")
        if "active_power_kw" not in merged:
            raise KeyError("historical data must include active_power_kw column")
        merged["target"] = merged["active_power_kw"].shift(-96)
        merged["lag_96"] = merged["active_power_kw"].shift(96)
        merged["lag_192"] = merged["active_power_kw"].shift(192)
        merged = merged.drop(columns=["active_power_kw"])
        merged["hour"] = merged.index.hour
        merged["month"] = merged.index.month
        merged["is_weekend"] = merged.index.weekday >= 5
        merged = merged.dropna()
        return merged

    def _build_forecast_features(self, weather_forecast: pd.DataFrame, reference_profile: pd.Series) -> pd.DataFrame:
        df = weather_forecast.copy()
        df["hour"] = df.index.hour
        df["month"] = df.index.month
        df["is_weekend"] = df.index.weekday >= 5
        ref = reference_profile.sort_index()
        if ref.index.tz != df.index.tz:
            ref = ref.tz_convert(df.index.tz)
        lag_1_day = ref.reindex(df.index - timedelta(days=1))
        lag_2_day = ref.reindex(df.index - timedelta(days=2))
        if lag_1_day.isna().any() or lag_2_day.isna().any():
            raise ValueError("Reference profile missing required historical intervals")
        df["lag_96"] = lag_1_day.values
        df["lag_192"] = lag_2_day.values
        return df


def combine_weather_sources(sources: Iterable[pd.DataFrame]) -> pd.DataFrame:
    data = pd.concat(sources, axis=1)
    data = data.groupby(level=0, axis=1).mean()
    return data.interpolate(limit_direction="both")
