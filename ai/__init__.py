"""LLM-driven orchestration helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_PATH = Path("config") / "ai.yaml"


def load_ai_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load AI orchestration configuration."""
    cfg_path = path or CONFIG_PATH
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    return {}


__all__ = ["load_ai_config"]
