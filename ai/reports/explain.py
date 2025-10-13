from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..prompts import EXPLAIN_FORECAST_PROMPT
from ..providers.gpt import GPTProvider
from ..providers.claude import ClaudeProvider

logger = logging.getLogger(__name__)


class ForecastExplainer:
    """Generate Markdown explanations for forecast runs."""

    def __init__(self, config: Optional[Dict[str, Any]], providers_registry) -> None:
        cfg = config or {}
        provider_cfg = cfg.get("providers", {})
        self.providers = {
            "openai": providers_registry.gpt if providers_registry else GPTProvider(provider_cfg.get("openai")),
            "anthropic": providers_registry.claude if providers_registry else ClaudeProvider(provider_cfg.get("anthropic")),
        }
        self.temperature = cfg.get("llm", {}).get("temperature", 0.3)

    def explain_forecast(self, context: Dict[str, Any]) -> str:
        provider = next((p for p in self.providers.values() if p and p.is_available()), None)
        render = EXPLAIN_FORECAST_PROMPT.render(
            site_name=context.get("site", {}).get("name", "Unnamed site"),
            window=context.get("forecast_window", "n/a"),
            model=context.get("selected_model", "unknown"),
            expected_mape=context.get("metrics", {}).get("expected_mape", "n/a"),
            weather_regime=context.get("weather_regime", "unknown"),
            metrics=context.get("metrics", {}),
            uncertainty_band=context.get("uncertainty_band", "±10%"),
            data_quality=context.get("data_quality_flags"),
        )

        if provider:
            try:
                return provider.chat(render["system"], render["user"], temperature=self.temperature)
            except Exception as exc:  # pragma: no cover
                logger.warning("LLM explanation failed (%s); using rule-based text.", exc)

        return self._fallback_markdown(context)

    @staticmethod
    def _fallback_markdown(context: Dict[str, Any]) -> str:
        model = context.get("selected_model", "unknown")
        window = context.get("forecast_window", "n/a")
        mape = context.get("metrics", {}).get("expected_mape", "n/a")
        weather = context.get("weather_regime", "unknown")
        uncertainty = context.get("uncertainty_band", "±10%")
        data_quality = context.get("data_quality_flags") or []

        return (
            f"### Forecast Summary\n"
            f"- Model: **{model}** for window `{window}` (expected MAPE {mape}%).\n"
            f"- Weather regime: **{weather}**; anticipate variability within {uncertainty}.\n"
            f"- Data quality issues: {', '.join(data_quality) if data_quality else 'none'}.\n"
            f"- Recommendation: monitor production vs forecast, adjust intraday bids if deviation > {uncertainty}."
        )
