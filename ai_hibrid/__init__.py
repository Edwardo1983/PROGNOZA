"""Hybrid physics + ML PV forecasting package."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .pipeline.dataset import build_training_dataset
from .pipeline.train import train_pipeline
from .pipeline.predict import predict_pipeline

__all__ = [
    "build_training_dataset",
    "train_pipeline",
    "predict_pipeline",
]

PACKAGE_ROOT = Path(__file__).resolve().parent


def default_config_path() -> Path:
    return PACKAGE_ROOT / "config" / "hybrid.yaml"


def load_default_config() -> Dict[str, Any]:
    from .pipeline.utils import load_config

    return load_config(default_config_path())
