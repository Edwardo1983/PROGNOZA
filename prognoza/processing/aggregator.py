"""Agregare seriilor de timp pentru profiluri 15 min si 1h."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd


def aggregate(data: pd.DataFrame, frequency: str, metrics: Dict[str, str] | None = None) -> pd.DataFrame:
    if data.empty:
        raise ValueError("Input data is empty")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Input data must use a DatetimeIndex")
    metrics = metrics or {col: "mean" for col in data.columns}
    resampled = data.resample(frequency).agg(metrics)
    return resampled


def ensure_full_day(profile: pd.DataFrame, delivery_day: datetime) -> pd.DataFrame:
    start = pd.Timestamp(delivery_day.date(), tz=profile.index.tz)
    freq = profile.index.freq or pd.tseries.frequencies.to_offset("15min")
    required = pd.date_range(start=start, periods=96, freq=freq)
    profile = profile.reindex(required)
    profile = profile.ffill().bfill()
    return profile


def prepare_notification_series(data: pd.DataFrame, delivery_day: datetime) -> pd.DataFrame:
    fifteen = aggregate(data, "15min", {"active_power_kw": "mean"})
    fifteen = ensure_full_day(fifteen, delivery_day)
    fifteen["planned_mw"] = fifteen["active_power_kw"] / 1000
    return fifteen[["planned_mw", "active_power_kw"]]
