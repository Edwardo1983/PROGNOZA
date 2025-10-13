"""Application level smoke tests."""

from __future__ import annotations

import pytest

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for app module")


def test_app_health_endpoint_absent() -> None:
    """Skip gracefully when no HTTP application is defined."""
    logger.info("No dedicated FastAPI application exposed in app package; skipping")
    pytest.skip("app package does not expose a FastAPI application")
