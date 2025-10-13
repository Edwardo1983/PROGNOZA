"""Validation tests for automation scripts repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for scripts module")


@pytest.fixture(scope="module")
def scripts_root(project_root: Path) -> Path:
    path = project_root / "scripts"
    if not path.exists():
        pytest.skip("scripts directory missing")
    return path


def test_scripts_catalog_contains_weather_helpers(scripts_root: Path) -> None:
    """Ensure bundled PowerShell helpers for weather fetching are present."""
    logger.info("Inspecting scripts catalog")
    power_shell_scripts = list(scripts_root.glob("fetch_weather_*.ps1"))
    assert power_shell_scripts, "Expected PowerShell weather scripts to exist"
    for script in power_shell_scripts:
        contents = script.read_text(encoding="utf-8")
        assert "weather" in contents.lower()
