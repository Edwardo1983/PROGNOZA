"""Time alignment utilities for 1-minute Janitza CSV exports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo


@dataclass
class AlignmentMetrics:
    monotonic: bool
    duplicates: int
    invalid: int
    drift_seconds: pd.Series
    late_mask: pd.Series
    drift_summary: Dict[str, float]
    late_rate: float


def add_time_columns(
    frame: pd.DataFrame,
    timezone: str,
    *,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Ensure timestamp columns exist in both UTC and configured local timezone."""
    if timestamp_col not in frame.columns:
        raise ValueError(f"CSV missing required '{timestamp_col}' column")

    working = frame.copy()
    parsed = pd.to_datetime(working[timestamp_col], errors="coerce", utc=False)
    invalid_mask = parsed.isna()

    tz = ZoneInfo(timezone)
    try:
        # When the parsed series is timezone-aware we convert, otherwise localise first.
        if getattr(parsed.dt, "tz", None) is None:
            localized = parsed.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
        else:
            localized = parsed.dt.tz_convert(tz)
    except (TypeError, ValueError):
        # Fallback: treat as UTC and convert to target TZ.
        localized = parsed.dt.tz_localize("UTC", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert(tz)

    working["timestamp_local"] = localized
    working["timestamp_utc"] = localized.dt.tz_convert("UTC")
    working["timestamp_invalid"] = invalid_mask

    return working


def compute_alignment_metrics(
    timestamps_utc: pd.Series,
    drift_sec_max: float,
) -> AlignmentMetrics:
    """Calculate drift against minute boundaries and monotonicity helpers."""
    valid = timestamps_utc.dropna()
    monotonic = valid.is_monotonic_increasing

    duplicates = int(valid.duplicated().sum())
    invalid = int(timestamps_utc.isna().sum())

    if valid.empty:
        empty = pd.Series(dtype="float64")
        summary = {"mean": 0.0, "p95": 0.0, "max": 0.0}
        return AlignmentMetrics(
            monotonic=monotonic,
            duplicates=duplicates,
            invalid=invalid,
            drift_seconds=empty,
            late_mask=pd.Series(dtype=bool),
            drift_summary=summary,
            late_rate=0.0,
        )

    rounded = valid.dt.round("min")
    drift = (valid - rounded).dt.total_seconds()
    drift = drift.astype("float64").fillna(0.0)
    abs_drift = drift.abs()
    late_mask = abs_drift > float(drift_sec_max)

    summary = {
        "mean": float(abs_drift.mean()) if len(abs_drift) else 0.0,
        "p95": float(abs_drift.quantile(0.95)) if len(abs_drift) else 0.0,
        "max": float(abs_drift.max()) if len(abs_drift) else 0.0,
    }

    late_rate = float(late_mask.mean()) if len(late_mask) else 0.0

    drift_series = pd.Series(drift, index=valid.index)
    late_series = pd.Series(late_mask, index=valid.index)

    return AlignmentMetrics(
        monotonic=monotonic,
        duplicates=duplicates,
        invalid=invalid,
        drift_seconds=drift_series,
        late_mask=late_series,
        drift_summary=summary,
        late_rate=late_rate,
    )


def detect_missing_minutes(timestamps_utc: pd.Series) -> Dict[str, object]:
    """Return statistics about missing minute slots."""
    valid = timestamps_utc.dropna()
    if valid.empty:
        empty_index = pd.DatetimeIndex([], tz="UTC")
        return {
            "expected_count": 0,
            "missing_count": 0,
            "missing_minutes": [],
            "minute_index": empty_index,
            "full_range": empty_index,
        }

    rounded = valid.dt.round("min")
    rounded = rounded.sort_values()
    unique_minutes = rounded.drop_duplicates()
    start = unique_minutes.iloc[0]
    end = unique_minutes.iloc[-1]

    full_range = pd.date_range(start=start, end=end, freq="min")
    missing = full_range.difference(unique_minutes)

    return {
        "expected_count": int(len(full_range)),
        "missing_count": int(len(missing)),
        "missing_minutes": [ts.isoformat() for ts in missing],
        "minute_index": unique_minutes,
        "full_range": full_range,
    }


def build_alignment_overview(
    timestamps_utc: pd.Series,
    drift_sec_max: float,
) -> Dict[str, object]:
    metrics = compute_alignment_metrics(timestamps_utc, drift_sec_max)
    gaps = detect_missing_minutes(timestamps_utc)

    total_minutes = gaps["expected_count"] or len(metrics.drift_seconds)
    missing_rate = float(gaps["missing_count"] / total_minutes) if total_minutes else 0.0

    return {
        "metrics": metrics,
        "gaps": gaps,
        "missing_rate": missing_rate,
    }


def alignment_issue_strings(overview: Dict[str, object], drift_sec_max: float) -> List[str]:
    """Generate human readable issues for inclusion in validation output."""
    issues: List[str] = []
    metrics: AlignmentMetrics = overview["metrics"]
    gaps: Dict[str, object] = overview["gaps"]

    if metrics.invalid:
        issues.append(f"{metrics.invalid} timestamps failed to parse")
    if not metrics.monotonic:
        issues.append("Timestamps are not strictly monotonic increasing")
    if metrics.duplicates:
        issues.append(f"{metrics.duplicates} duplicate minute timestamps detected")
    late_count = int(metrics.late_mask.sum())
    if late_count:
        issues.append(f"{late_count} samples drift past ±{drift_sec_max}s")
    if gaps["missing_count"]:
        issues.append(f"{gaps['missing_count']} minute slots missing within captured timeframe")
    return issues


def histogram(values: Iterable[float], bins: int = 20) -> Dict[str, List[float]]:
    """Return histogram buckets useful for plotting sparklines."""
    array = np.asarray(list(values), dtype="float64")
    if array.size == 0:
        return {"bins": [], "counts": []}
    counts, bin_edges = np.histogram(array, bins=bins)
    return {
        "bins": bin_edges.tolist(),
        "counts": counts.astype(int).tolist(),
    }
