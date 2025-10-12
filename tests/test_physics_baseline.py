from __future__ import annotations

import pandas as pd

from ai_hibrid.models.physics_baseline import physics_power


def test_physics_baseline_simple() -> None:
    config = {
        "system": {
            "kWp": 5.0,
            "gamma_Pmp": -0.004,
            "bos_loss": 0.05,
        }
    }
    index = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    poa = pd.Series([0, 600, 1000], index=index)
    t_cell = pd.Series([25, 35, 45], index=index)

    power = physics_power(poa, t_cell, config)

    # At STC should be close to nominal after derate
    assert power.iloc[0] == 0
    assert power.iloc[1] > power.iloc[0]
    assert power.iloc[2] < 5000  # clipping due to temperature and derate
