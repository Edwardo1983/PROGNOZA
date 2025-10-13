"""Utility helpers for the hybrid pipeline."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

TIMEZONE_ALIASES: Dict[str, str] = {
    "europe/brezoaia": "Europe/Bucharest",
    "brezoaia": "Europe/Bucharest",
}


def load_config(path: Path | str) -> Dict[str, Any]:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    site = data.get("site")
    if isinstance(site, dict):
        timezone = site.get("timezone")
        if isinstance(timezone, str):
            normalized = _normalize_timezone(timezone)
            if normalized != timezone:
                logger.info("Normalised site timezone '%s' → '%s'", timezone, normalized)
            site["timezone"] = normalized
    return data


def ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _expand_measurement_path(path: Path) -> Path:
    """Resolve a measurement file path with helpful fallbacks."""
    if path.exists():
        return path

    if path.is_dir():
        candidates = sorted(path.glob("*.csv"))
        if not candidates:
            raise FileNotFoundError(f"No CSV files found in directory '{path}'")
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        logger.info("Using latest measurement CSV '%s' from directory '%s'", latest.name, path)
        return latest

    search_token = _extract_date_token(path.name)
    search_roots: List[Path] = [
        path.parent,
        Path("data") / "exports",
        Path("data") / "raw",
    ]
    seen: set[Path] = set()
    candidates: List[Path] = []
    for root in search_roots:
        if not root or not root.exists():
            continue
        for candidate in root.glob("*.csv"):
            if candidate in seen:
                continue
            seen.add(candidate)
            if search_token and search_token in candidate.name:
                candidates.append(candidate)
            elif candidate.name == path.name:
                candidates.append(candidate)

    if not candidates:
        hint = f" containing '{search_token}'" if search_token else ""
        raise FileNotFoundError(
            f"Measurement file '{path}' not found and no fallback CSV{hint} discovered."
        )
    if len(candidates) > 1:
        formatted = "\n".join(f"  - {candidate}" for candidate in candidates)
        raise FileNotFoundError(
            "Multiple measurement CSV candidates matched the request; please specify one explicitly:\n"
            f"{formatted}"
        )

    resolved = candidates[0]
    logger.info("Resolved measurement path '%s' → '%s'", path, resolved)
    return resolved


def _extract_date_token(name: str) -> Optional[str]:
    match = re.search(r"\d{4}-\d{2}-\d{2}", name)
    if match:
        return match.group(0)
    return None


def _normalize_timezone(value: str) -> str:
    alias = TIMEZONE_ALIASES.get(value.lower())
    return alias or value


def read_measurements(path: Path | str) -> pd.DataFrame:
    resolved = _expand_measurement_path(Path(path))
    df = pd.read_csv(resolved)
    if "timestamp" not in df.columns:
        raise ValueError("Measurement CSV must contain a 'timestamp' column")
    if "power_W" not in df.columns:
        power_candidates = [
            "power_active_total",
            "power_active_sum",
            "active_power_total",
            "power_total_w",
        ]
        replacement = next((col for col in power_candidates if col in df.columns), None)
        if replacement:
            logger.info("Using '%s' column as power_W for measurements", replacement)
            df["power_W"] = pd.to_numeric(df[replacement], errors="coerce")
        else:
            raise ValueError("Measurement CSV must contain a 'power_W' column or a recognised power total column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")
    return df


def _resolve_weather_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.suffix.lower() == ".csv":
        parquet_candidate = path.with_suffix(".parquet")
        if parquet_candidate.exists():
            logger.info("Using Parquet weather data '%s' instead of missing CSV '%s'", parquet_candidate, path)
            return parquet_candidate
    search_roots = [path.parent, Path("data") / "weather"]
    for root in search_roots:
        if not root or not root.exists():
            continue
        for candidate in root.glob(f"{path.stem}.*"):
            if candidate.suffix.lower() in {".parquet", ".csv"}:
                logger.info("Resolved weather path '%s' → '%s'", path, candidate)
                return candidate
    raise FileNotFoundError(f"Weather data file '{path}' not found")


def read_weather(path: Path | str) -> pd.DataFrame:
    resolved = _resolve_weather_path(Path(path))
    if resolved.suffix.lower() == ".parquet":
        df = pd.read_parquet(resolved)
    else:
        df = pd.read_csv(resolved)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    else:
        df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()


def save_json(data: Dict[str, Any], path: Path | str) -> None:
    path = Path(path)
    ensure_directory(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
