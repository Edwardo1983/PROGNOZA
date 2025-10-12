"""Time based feature engineering for PV forecasting."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
import pvlib


def build_time_features(
    timestamps: pd.DatetimeIndex,
    *,
    latitude: float,
    longitude: float,
    timezone: str,
) -> pd.DataFrame:
    """Return a dataframe with cyclic time features and solar position."""
    if not isinstance(timestamps, pd.DatetimeIndex):
        raise TypeError("timestamps must be a pandas.DatetimeIndex")
    if timestamps.tz is None:
        timestamps = timestamps.tz_localize("UTC").tz_convert(timezone)
    else:
        timestamps = timestamps.tz_convert(timezone)

    solar_position = pvlib.solarposition.get_solarposition(
        time=timestamps,
        latitude=latitude,
        longitude=longitude,
        method="nrel_numpy",
        pressure=None,
        temperature=25.0,
    )

    hour_rad = (timestamps.hour + timestamps.minute / 60.0) * (2 * math.pi / 24)
    doy = timestamps.dayofyear
    doy_rad = doy * (2 * math.pi / 366)

    data = pd.DataFrame(
        {
            "hour_sin": np.sin(hour_rad),
            "hour_cos": np.cos(hour_rad),
            "doy_sin": np.sin(doy_rad),
            "doy_cos": np.cos(doy_rad),
            "is_weekend": (timestamps.weekday >= 5).astype(int),
            "solar_zenith": solar_position["zenith"].values,
            "solar_azimuth": solar_position["azimuth"].values,
            "solar_elevation": 90.0 - solar_position["zenith"].values,
        },
        index=timestamps.tz_convert("UTC"),
    )
    return data
