"""Constructia notificarii fizice conform PO TEL-133."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

import pandas as pd

from prognoza.config.settings import PREInfo


@dataclass(slots=True)
class IntervalEntry:
    start: datetime
    end: datetime
    power_mw: float


@dataclass(slots=True)
class PhysicalNotification:
    cod_pre: str
    cod_brp: str
    delivery_day: datetime
    resolution: str
    aggregated_mw: float
    intervals: List[IntervalEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "cod_pre": self.cod_pre,
            "cod_brp": self.cod_brp,
            "delivery_day": self.delivery_day.strftime("%Y-%m-%d"),
            "resolution": self.resolution,
            "aggregated_mw": self.aggregated_mw,
            "intervals": [
                {
                    "start": interval.start.isoformat(),
                    "end": interval.end.isoformat(),
                    "power_mw": round(interval.power_mw, 3),
                }
                for interval in self.intervals
            ],
        }


def build_notification(pre: PREInfo, profile: pd.Series, resolution: str = "15min") -> PhysicalNotification:
    if profile.empty:
        raise ValueError("Profile must not be empty")
    if not isinstance(profile.index, pd.DatetimeIndex):
        raise ValueError("Profile index must be DatetimeIndex")
    intervals: List[IntervalEntry] = []
    total = 0.0
    for timestamp, value in profile.sort_index().items():
        end = timestamp + pd.tseries.frequencies.to_offset(resolution)
        total += value
        intervals.append(
            IntervalEntry(
                start=timestamp.to_pydatetime(),
                end=end.to_pydatetime(),
                power_mw=float(value),
            )
        )
    aggregated = total / len(intervals) if intervals else 0.0
    return PhysicalNotification(
        cod_pre=pre.cod_pre,
        cod_brp=pre.cod_brp,
        delivery_day=profile.index[0].to_pydatetime(),
        resolution=resolution,
        aggregated_mw=aggregated,
        intervals=intervals,
    )
