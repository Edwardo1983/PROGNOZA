from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from ai.orchestrator import AIOrchestrator


class DummyProvider:
    def __init__(self) -> None:
        self.available = True
        self.last_prompt: Dict[str, str] | None = None
        self.response_queue = ["hybrid_blend"]

    def is_available(self) -> bool:
        return self.available

    def chat(self, system: str, user: str, *, temperature: float = 0.0) -> str:
        self.last_prompt = {"system": system, "user": user, "temperature": temperature}
        if not self.response_queue:
            return "hybrid_blend"
        return self.response_queue.pop(0)


@pytest.fixture
def orchestrator(monkeypatch) -> AIOrchestrator:
    dummy_provider = DummyProvider()

    from ai.policies.selection import ProviderRegistry

    def fake_init(self, config=None):
        self.config = config or {}
        self.provider_registry = ProviderRegistry(gpt=dummy_provider, claude=dummy_provider)
        self.temperature = 0.1

    monkeypatch.setattr("ai.policies.selection.ModelSelector.__init__", fake_init, raising=False)
    monkeypatch.setattr("ai.policies.selection.ModelSelector.select_model", lambda self, ctx: {"choice": "hybrid_blend", "confidence": 0.9, "source": "rules", "rationale": "test"})

    from ai.policies.drift import DriftAnalyzer

    def fake_drift(self, config=None):
        self.providers = {"openai": dummy_provider}
        self.temperature = 0.1

    monkeypatch.setattr(DriftAnalyzer, "__init__", fake_drift, raising=False)
    monkeypatch.setattr(DriftAnalyzer, "drift_summary", lambda self, ref, cur: {"drift_score": 0.1, "top_features": [], "narrative_md": "ok"})

    from ai.reports.explain import ForecastExplainer

    def fake_explainer(self, config, registry):
        self.providers = {"openai": dummy_provider}
        self.temperature = 0.1

    monkeypatch.setattr(ForecastExplainer, "__init__", fake_explainer, raising=False)
    monkeypatch.setattr(ForecastExplainer, "explain_forecast", lambda self, ctx: "### Forecast Summary\n- Test explanation.")

    return AIOrchestrator(config={})


def test_select_model(orchestrator: AIOrchestrator):
    context = {
        "metrics": {"mape_intraday": 4.5, "mape_dayahead": 5.0},
        "weather_regime": "clear",
    }
    decision = orchestrator.select_model(context)
    assert decision["choice"] in {"physics", "ml_xgb", "hybrid_blend"}
    assert "confidence" in decision


def test_explain_forecast(orchestrator: AIOrchestrator):
    context = {"selected_model": "hybrid_blend", "forecast_window": "2025-10-13T00Z/24h"}
    md = orchestrator.explain_forecast(context)
    assert md.startswith("### Forecast Summary")
