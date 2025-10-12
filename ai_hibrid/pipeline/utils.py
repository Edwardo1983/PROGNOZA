"""Utility helpers for the hybrid pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml


def load_config(path: Path | str) -> Dict[str, Any]:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_measurements(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise ValueError("Measurement CSV must contain a 'timestamp' column")
    if "power_W" not in df.columns:
        raise ValueError("Measurement CSV must contain a 'power_W' column")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")
    return df


def read_weather(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
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
