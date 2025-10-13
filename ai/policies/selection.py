from __future__ import annotations

import logging
from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional

from ..prompts import MODEL_SELECTION_PROMPT
from ..providers.gpt import GPTProvider
from ..providers.claude import ClaudeProvider

logger = logging.getLogger(__name__)

MODEL_CHOICES = ["physics", "ml_xgb", "hybrid_blend"]


def _confidence_from_metrics(intraday: float, dayahead: float) -> float:
    score = max(intraday, dayahead)
    if score <= 5:
        return 0.9
    if score <= 8:
        return 0.7
    if score <= 12:
        return 0.5
    if score <= 15:
        return 0.3
    return 0.1


@dataclass
class ProviderRegistry:
    gpt: GPTProvider
    claude: ClaudeProvider

    def first_available(self) -> Optional[object]:
        for provider in (self.gpt, self.claude):
            if provider.is_available():
                return provider
        return None


class ModelSelector:
    """Rule-based selector with optional LLM tie-break."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        provider_cfg = cfg.get("providers", {})
        self.provider_registry = ProviderRegistry(
            gpt=GPTProvider(provider_cfg.get("openai")),
            claude=ClaudeProvider(provider_cfg.get("anthropic")),
        )
        self.temperature = cfg.get("llm", {}).get("temperature", 0.3)

    def select_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        metrics = context.get("metrics", {})
        intraday = float(metrics.get("mape_intraday", 999.0))
        dayahead = float(metrics.get("mape_dayahead", 999.0))
        weather_regime = (context.get("weather_regime") or "unknown").lower()
        quality_flags: List[str] = context.get("data_quality_flags") or []

        decision = self._rule_based_choice(intraday, dayahead, weather_regime, quality_flags)
        confidence = decision["confidence"]
        choice = decision["choice"]

        if confidence < 0.6:
            provider = self.provider_registry.first_available()
            if provider:
                try:
                    llm_choice = self._llm_tie_break(provider, context, decision)
                    if llm_choice in MODEL_CHOICES:
                        decision["choice"] = llm_choice
                        decision["source"] = "llm"
                        decision["confidence"] = max(confidence, 0.7)
                except Exception as exc:  # pragma: no cover
                    logger.warning("LLM tie-break failed (%s)", exc)
        return decision

    def _rule_based_choice(
        self,
        intraday: float,
        dayahead: float,
        weather_regime: str,
        quality_flags: List[str],
    ) -> Dict[str, Any]:
        choice = "hybrid_blend"
        rationale = "Hybrid blend offers balanced performance."

        confidence = _confidence_from_metrics(intraday, dayahead)
        high_quality = not quality_flags

        if weather_regime in {"clear", "stable"} and intraday < 5 and high_quality:
            choice = "physics"
            confidence = max(confidence, 0.85)
            rationale = "Clear-sky regime favours deterministic physics baseline."
        elif "sensor_dropouts" in quality_flags or "missing_weather" in quality_flags:
            choice = "physics"
            confidence = 0.75
            rationale = "Data quality issues detected; physics baseline safest."
        elif intraday < 7 and dayahead < 9 and high_quality:
            choice = "ml_xgb"
            confidence = max(confidence, 0.8)
            rationale = "ML model performing well on recent validation."
        elif weather_regime in {"storm", "high winds"}:
            choice = "hybrid_blend"
            confidence = max(confidence, 0.7)
            rationale = "Blend dampens volatility under extreme weather."

        return {"choice": choice, "confidence": confidence, "source": "rules", "rationale": rationale}

    def _llm_tie_break(self, provider: object, context: Dict[str, Any], prev: Dict[str, Any]) -> str:
        render = MODEL_SELECTION_PROMPT.render(
            intraday_mape=context.get("metrics", {}).get("mape_intraday", "n/a"),
            dayahead_mape=context.get("metrics", {}).get("mape_dayahead", "n/a"),
            weather_regime=context.get("weather_regime", "unknown"),
            quality_flags=context.get("data_quality_flags", []),
        )
        raw = provider.chat(render["system"], render["user"], temperature=self.temperature)
        logger.debug("LLM tie-break raw output: %s", raw)
        try:
            data: Dict[str, Any] = json.loads(raw)  # type: ignore[arg-type]
        except Exception:
            return prev["choice"]
        choice = data.get("choice", "").strip()
        rationale = data.get("rationale")
        if choice in MODEL_CHOICES and rationale:
            prev["rationale"] = rationale
        return choice
