"""Data quality validation and repair for Janitza CSV exports."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yaml

from . import alignment, ranges
from .ntp_check import ntp_check
from .repair import repair_dataframe

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "data_quality.yaml"


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Data quality config not found at {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _analyse(prepared: pd.DataFrame, cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], list[str], Dict[str, Any]]:
    timezone = cfg.get("timezone", "UTC")
    drift_sec_max = float(cfg.get("drift_sec_max", 3))
    overview = alignment.build_alignment_overview(prepared["timestamp_utc"], drift_sec_max)
    metrics = overview["metrics"]
    gaps = overview["gaps"]

    minute_presence = {"timestamps": [], "present": []}
    full_range = gaps.get("full_range")
    minute_index = gaps.get("minute_index")
    if isinstance(full_range, pd.DatetimeIndex) and len(full_range):
        present_mask = full_range.isin(minute_index)
        minute_presence = {
            "timestamps": [ts.isoformat() for ts in full_range],
            "present": present_mask.astype(int).tolist(),
        }

    range_eval = ranges.evaluate_ranges(prepared, cfg.get("ranges", {}))
    stats = {
        "row_count": int(len(prepared)),
        "missing_rate": float(overview["missing_rate"]),
        "late_rate": float(metrics.late_rate),
        "drift_secs": metrics.drift_summary,
        "outlier_rate": float(range_eval["outlier_rate"]),
        "value_ranges": range_eval["violations"],
        "ranges_total_outliers": int(range_eval["total_outliers"]),
        "alignment_histogram": alignment.histogram(metrics.drift_seconds),
        "late_samples": (
            prepared.loc[metrics.late_mask[metrics.late_mask].index, "timestamp"].tolist()
            if metrics.late_mask.any()
            else []
        ),
        "missing_minutes": gaps.get("missing_minutes", []),
        "missing_map": minute_presence,
        "timezone": timezone,
    }

    ts_utc = prepared["timestamp_utc"].dropna()
    if not ts_utc.empty:
        stats["start_utc"] = ts_utc.iloc[0].isoformat()
        stats["end_utc"] = ts_utc.iloc[-1].isoformat()
    else:
        stats["start_utc"] = None
        stats["end_utc"] = None

    stats["start_local"] = (
        prepared["timestamp_local"].dropna().iloc[0].isoformat()
        if "timestamp_local" in prepared and not prepared["timestamp_local"].dropna().empty
        else None
    )
    stats["end_local"] = (
        prepared["timestamp_local"].dropna().iloc[-1].isoformat()
        if "timestamp_local" in prepared and not prepared["timestamp_local"].dropna().empty
        else None
    )

    issues = alignment.alignment_issue_strings(overview, drift_sec_max)
    if range_eval["total_outliers"]:
        issues.append(
            f"{range_eval['total_outliers']} values outside configured ranges "
            f"across {len(range_eval['violations'])} columns"
        )

    if metrics.invalid:
        stats["invalid_timestamps"] = metrics.invalid

    analysis = {
        "overview": overview,
        "ranges": range_eval,
    }
    return stats, issues, analysis


def _prepare_frame(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    tz = cfg.get("timezone", "UTC")
    prepared = alignment.add_time_columns(df, tz)
    prepared = prepared.sort_values("timestamp_utc").reset_index(drop=True)
    return prepared


def validate_csv(path: Path | str, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or load_config()
    frame = pd.read_csv(path)
    prepared = _prepare_frame(frame, cfg)
    stats, issues, analysis = _analyse(prepared, cfg)

    result = {
        "ok": not issues,
        "issues": issues,
        "stats": stats,
    }

    if cfg.get("enable_ntp_check"):
        try:
            ntp_result = ntp_check()
            result["stats"]["ntp_offset_ms"] = ntp_result["offset_ms"]
            if not ntp_result["ok"]:
                result["issues"].append("NTP offset exceeds ±1s")
                result["ok"] = False
        except Exception as exc:  # pragma: no cover - network hiccups
            result["issues"].append(f"NTP check failed: {exc}")
            result["ok"] = False

    result["analysis"] = analysis
    return result


def auto_repair_csv(
    in_path: Path | str,
    out_path: Path | str,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = cfg or load_config()
    in_path = Path(in_path)
    out_path = Path(out_path)

    original_frame = pd.read_csv(in_path)
    prepared_original = _prepare_frame(original_frame, cfg)
    original_stats, original_issues, original_analysis = _analyse(prepared_original, cfg)
    original_result = {
        "ok": not original_issues,
        "issues": original_issues,
        "stats": original_stats,
        "analysis": original_analysis,
    }

    forward_fill_max = int(cfg.get("forward_fill_max", 2))
    repaired_prepared, repair_meta = repair_dataframe(
        prepared_original,
        timezone=cfg.get("timezone", "UTC"),
        forward_fill_max=forward_fill_max,
    )
    repaired_stats, repaired_issues, repaired_analysis = _analyse(repaired_prepared, cfg)
    repaired_result = {
        "ok": not repaired_issues,
        "issues": repaired_issues,
        "stats": repaired_stats,
        "analysis": repaired_analysis,
    }

    # Persist repaired CSV while preserving column order
    output_df = repaired_prepared.copy()
    drop_cols = [col for col in ("timestamp_local", "timestamp_utc", "timestamp_invalid") if col in output_df.columns]
    if drop_cols:
        output_df = output_df.drop(columns=drop_cols)
    cols = output_df.columns.tolist()
    if "timestamp" in cols:
        cols.insert(0, cols.pop(cols.index("timestamp")))
        output_df = output_df.loc[:, cols]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(out_path, index=False)

    from . import report as report_module  # late import to avoid circular

    def _strip_analysis(block: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in block.items() if key != "analysis"}

    payload = report_module.build_payload(
        config=cfg,
        input_csv=in_path,
        output_csv=out_path,
        original=_strip_analysis(original_result),
        repaired=_strip_analysis(repaired_result),
        repair=repair_meta,
    )
    report_paths = report_module.write_reports(out_path, payload)

    return {
        "input": original_result,
        "output": repaired_result,
        "repair": repair_meta,
        "reports": report_paths,
    }


__all__ = [
    "load_config",
    "validate_csv",
    "auto_repair_csv",
    "ntp_check",
]
