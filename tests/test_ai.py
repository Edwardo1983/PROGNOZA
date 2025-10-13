"""Unit tests for the AI orchestrator facade."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.conftest import get_test_logger

logger = get_test_logger(__name__)
logger.info("Starting tests for AI orchestrator module")


def test_ai_orchestrator_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure orchestrator delegates to mocked strategy components."""
    from ai import orchestrator as orchestrator_module

    logger.info("Running AI orchestrator delegation test")

    class DummySelector:
        def __init__(self, config):
            self.config = config
            self.provider_registry = SimpleNamespace(first_available=lambda: None)

        def select_model(self, context):
            return {"choice": "physics", "confidence": 0.95, "source": "rules"}

    class DummyDriftAnalyzer:
        def __init__(self, config):
            self.config = config

        def drift_summary(self, ref_stats, cur_stats):
            return {"drift_score": 0.12, "top_features": ["temp_C", "ghi_Wm2"]}

    class DummyExplainer:
        def __init__(self, config, registry):
            self.config = config
            self.registry = registry

        def explain_forecast(self, context):
            return "## Forecast rationale\n- Stable outlook"

    monkeypatch.setattr(orchestrator_module, "ModelSelector", DummySelector)
    monkeypatch.setattr(orchestrator_module, "DriftAnalyzer", DummyDriftAnalyzer)
    monkeypatch.setattr(orchestrator_module, "ForecastExplainer", DummyExplainer)

    orchestrator = orchestrator_module.AIOrchestrator(config={})

    decision = orchestrator.select_model({"metrics": {"mape_intraday": 4.2}})
    assert decision["choice"] == "physics"
    assert decision["source"] == "rules"

    summary = orchestrator.summarize_drift({"reference_stats": {}, "current_stats": {}})
    assert pytest.approx(summary["drift_score"], rel=1e-3) == 0.12
    assert "temp_C" in summary["top_features"]

    explanation = orchestrator.explain_forecast({"forecast": []})
    assert explanation.startswith("## Forecast rationale")
