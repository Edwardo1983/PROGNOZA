"""Clear-sky irradiation estimates and simple PV thermal model."""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd
import pvlib


def _location_from_config(config: Dict[str, dict]) -> pvlib.location.Location:
    site = config.get("site", {})
    latitude = site.get("latitude")
    longitude = site.get("longitude")
    if latitude is None or longitude is None:
        raise ValueError("Config must include site.latitude and site.longitude")
    altitude = site.get("altitude")
    timezone = site.get("timezone", "UTC")
    return pvlib.location.Location(latitude=latitude, longitude=longitude, altitude=altitude, tz=timezone)


def compute_clearsky_poa(
    timestamps: pd.DatetimeIndex,
    weather: Optional[pd.DataFrame],
    config: Dict[str, dict],
) -> pd.DataFrame:
    """Return clearsky GHI/DNI/DHI, POA irradiance and cell temperature."""
    if timestamps.tz is None:
        raise ValueError("timestamps must be timezone-aware")

    location = _location_from_config(config)
    local_times = timestamps.tz_convert(location.tz)
    clearsky = location.get_clearsky(local_times, model="ineichen").tz_convert("UTC")
    solar_position = location.get_solarposition(local_times).tz_convert("UTC")

    system = config.get("system", {})
    tilt = system.get("tilt", 30.0)
    azimuth = system.get("azimuth", 180.0)

    dni_extra = pvlib.irradiance.get_extra_radiation(local_times, method="spencer").tz_convert("UTC")

    total_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        solar_zenith=solar_position["zenith"],
        solar_azimuth=solar_position["azimuth"],
        dni=clearsky["dni"],
        ghi=clearsky["ghi"],
        dhi=clearsky["dhi"],
        dni_extra=dni_extra,
        model="haydavies",
    )

    poa_global = total_irradiance["poa_global"].rename("poa_clearsky")
    result = pd.DataFrame(
        {
            "poa_clearsky": poa_global,
            "ghi_clearsky": clearsky["ghi"],
            "dni_clearsky": clearsky["dni"],
            "dhi_clearsky": clearsky["dhi"],
        }
    )
    result = result.fillna(0.0)

    if weather is None:
        weather = pd.DataFrame(index=result.index)

    weather_aligned = weather.reindex(result.index)
    weather_aligned = weather_aligned.apply(pd.to_numeric, errors="coerce")
    weather_aligned = weather_aligned.interpolate(limit_direction="both")
    temp_air = weather_aligned.get("temp_C", pd.Series(25.0, index=result.index))
    wind_speed = weather_aligned.get("wind_ms", pd.Series(1.0, index=result.index))

    temp_cfg = config.get("temperature_model", {})
    c1 = temp_cfg.get("c1", 0.035)
    c2 = temp_cfg.get("c2", -1.0)

    t_cell = temp_air + c1 * result["poa_clearsky"] + c2 * wind_speed
    result["t_cell"] = t_cell
    return result
