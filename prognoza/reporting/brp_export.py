"""Export profil comercial pentru BRP."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


BRP_HEADERS = ["Data", "Ora", "Putere_medie_kW", "Energie_kWh", "Calitate_semnal"]


def export_profile(profile: pd.Series, output: Path) -> None:
    if not isinstance(profile.index, pd.DatetimeIndex):
        raise ValueError("Profile index must be datetime")
    df = pd.DataFrame(index=profile.index)
    df["Putere_medie_kW"] = profile.values
    df["Energie_kWh"] = profile.values * 0.25
    df["Calitate_semnal"] = "OK"
    df["Data"] = df.index.date
    df["Ora"] = df.index.strftime("%H:%M")
    df = df[BRP_HEADERS]
    df.to_csv(output, index=False)
