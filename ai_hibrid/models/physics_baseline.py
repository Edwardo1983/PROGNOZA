"""Deterministic PV power baseline."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def physics_power(
    poa: pd.Series,
    cell_temperature: pd.Series,
    config: Dict[str, dict],
) -> pd.Series:
    """Compute baseline PV output using a simple efficiency curve."""
    system = config.get("system", {})
    kWp = float(system.get("kWp", 1.0))
    gamma = float(system.get("gamma_Pmp", -0.004))
    bos_loss = float(system.get("bos_loss", 0.05))
    derate = max(0.0, 1.0 - bos_loss)

    temp_delta = cell_temperature - 25.0
    ratio = (poa.clip(lower=0) / 1000.0) * (1.0 + gamma * temp_delta)
    power = kWp * 1000.0 * ratio * derate
    return power.clip(lower=0.0)


def physics_dataframe(
    clearsky: pd.DataFrame,
    config: Dict[str, dict],
) -> pd.DataFrame:
    """Helper returning power baseline along with clearsky inputs."""
    output = clearsky.copy()
    output["power_physics_W"] = physics_power(
        poa=clearsky["poa_clearsky"],
        cell_temperature=clearsky["t_cell"],
        config=config,
    )
    return output
