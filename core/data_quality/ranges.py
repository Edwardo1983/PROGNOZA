"""Value range validation for Janitza CSV exports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

DEFAULT_PATTERNS: Dict[str, Sequence[str]] = {
    "voltage_v": ("voltage",),
    "current_a": ("current",),
    "freq_hz": ("freq", "frequency"),
    "pf": ("pf", "power_factor"),
    "thd_pct": ("thd",),
}


@dataclass
class RangeConfig:
    minimum: Optional[float]
    maximum: Optional[float]
    columns: Sequence[str]


def _normalise_entry(key: str, value: object, columns: Iterable[str]) -> RangeConfig:
    if isinstance(value, dict):
        minimum = value.get("min")
        maximum = value.get("max")
        specified_cols = value.get("columns")
        patterns = value.get("patterns")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        minimum, maximum = value
        specified_cols = None
        patterns = None
    else:
        raise ValueError(f"Invalid range definition for '{key}' ({value!r})")

    if specified_cols:
        resolved_columns = [col for col in specified_cols if col in columns]
    else:
        resolved_columns = _match_columns(columns, patterns or DEFAULT_PATTERNS.get(key, (key,)))

    return RangeConfig(
        minimum=float(minimum) if minimum is not None else None,
        maximum=float(maximum) if maximum is not None else None,
        columns=resolved_columns,
    )


def _match_columns(columns: Iterable[str], patterns: Iterable[str]) -> List[str]:
    cols = []
    lowered = [col.lower() for col in columns]
    for pattern in patterns:
        pattern_low = pattern.lower()
        for original, low in zip(columns, lowered):
            if pattern_low in low and original not in cols:
                cols.append(original)
    return cols


def evaluate_ranges(frame: pd.DataFrame, config: Dict[str, object]) -> Dict[str, object]:
    """Validate value ranges using normalised configuration."""
    numeric_cols = frame.select_dtypes(include=[np.number]).columns.tolist()
    evaluated_cols: Dict[str, Dict[str, object]] = {}

    total_points = 0
    total_outliers = 0

    for key, value in config.items():
        normalised = _normalise_entry(key, value, frame.columns)
        target_cols = [col for col in normalised.columns if col in numeric_cols]
        if not target_cols:
            continue

        minimum = normalised.minimum
        maximum = normalised.maximum

        for col in target_cols:
            series = frame[col]
            if series.empty:
                continue
            mask = pd.Series(False, index=series.index)
            if minimum is not None:
                mask |= series < minimum
            if maximum is not None:
                mask |= series > maximum

            count = int(mask.sum())
            total_points += series.notna().sum()
            total_outliers += count

            if count:
                samples = series[mask].head(5)
                evaluated_cols[col] = {
                    "range_key": key,
                    "min_allowed": minimum,
                    "max_allowed": maximum,
                    "violations": count,
                    "sample_values": samples.tolist(),
                    "sample_timestamps": frame.loc[samples.index, "timestamp"].tolist()
                    if "timestamp" in frame.columns
                    else [],
                }

    outlier_rate = float(total_outliers / total_points) if total_points else 0.0

    return {
        "outlier_rate": outlier_rate,
        "violations": evaluated_cols,
        "total_outliers": total_outliers,
        "total_points": total_points,
    }
