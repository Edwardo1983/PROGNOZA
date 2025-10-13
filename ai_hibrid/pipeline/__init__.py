"""Pipeline orchestration helpers."""
from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "dataset",
    "train",
    "predict",
    "build_training_dataset",
    "build_feature_matrix",
    "train_pipeline",
    "predict_pipeline",
]

_LAZY_ATTRS = {
    "build_training_dataset": ("ai_hibrid.pipeline.dataset", "build_training_dataset"),
    "build_feature_matrix": ("ai_hibrid.pipeline.dataset", "build_feature_matrix"),
    "train_pipeline": ("ai_hibrid.pipeline.train", "train_pipeline"),
    "predict_pipeline": ("ai_hibrid.pipeline.predict", "predict_pipeline"),
}


def __getattr__(name: str) -> Any:
    if name in {"dataset", "train", "predict"}:
        return importlib.import_module(f"{__name__}.{name}")
    if name in _LAZY_ATTRS:
        module_name, attr = _LAZY_ATTRS[name]
        module = importlib.import_module(module_name)
        return getattr(module, attr)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
