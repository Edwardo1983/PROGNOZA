"""Repair helpers for Janitza CSV exports."""
from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

from . import alignment


def repair_dataframe(
    prepared: pd.DataFrame,
    *,
    timezone: str,
    forward_fill_max: int,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Fill short gaps and return repaired frame plus metadata."""
    if "timestamp_utc" not in prepared.columns:
        raise ValueError("Expected 'timestamp_utc' column in prepared dataframe")

    local_tz = ZoneInfo(timezone)
    working = prepared.copy()
    working = working.sort_values("timestamp_utc").reset_index(drop=True)

    index = pd.DatetimeIndex(working["timestamp_utc"]).tz_convert("UTC")
    if index.empty:
        return working, {
            "generated_rows": 0,
            "filled_cells": 0,
            "forward_fill_max": forward_fill_max,
        }

    start = index.min().floor("min")
    end = index.max().ceil("min")
    full_index = pd.date_range(start=start, end=end, freq="min", tz="UTC")

    working = working.set_index(index)
    reindexed = working.reindex(full_index)

    numeric_cols = reindexed.select_dtypes(include=[np.number]).columns
    pre_fill = reindexed[numeric_cols].copy()

    interpolated = pre_fill.interpolate(
        method="time",
        limit=forward_fill_max,
        limit_area="inside",
    )
    filled_numeric = interpolated.ffill(limit=forward_fill_max)
    reindexed[numeric_cols] = filled_numeric

    filled_cells = int(((pre_fill.isna()) & (reindexed[numeric_cols].notna())).sum().sum())
    generated_rows = int((~reindexed.index.isin(index)).sum())

    elapsed_minutes = ((reindexed.index - reindexed.index[0]).total_seconds() / 60.0).round(2)
    thresholds = (5, 10, 15, 30, 60)
    milestone_strings = [
        ";".join(str(t) for t in thresholds if value >= t) for value in elapsed_minutes
    ]

    reindexed["timestamp"] = reindexed.index.tz_convert(local_tz).map(lambda dt: dt.replace(microsecond=0).isoformat())
    reindexed["timestamp_local"] = reindexed["timestamp"]
    reindexed["timestamp_utc"] = reindexed.index.tz_convert("UTC").map(lambda dt: dt.replace(microsecond=0).isoformat())
    reindexed["elapsed_minutes"] = elapsed_minutes
    reindexed["milestones"] = milestone_strings
    reindexed["qa_generated"] = ~reindexed.index.isin(index)

    repaired = reindexed.reset_index(drop=True)
    repaired = repaired.sort_values("timestamp")

    metadata = {
        "generated_rows": generated_rows,
        "filled_cells": filled_cells,
        "forward_fill_max": forward_fill_max,
    }

    prepared_repaired = alignment.add_time_columns(repaired, timezone)
    return prepared_repaired, metadata
