from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from . import load_ai_config
from .policies.selection import ModelSelector
from .policies.drift import DriftAnalyzer
from .reports.explain import ForecastExplainer

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """Facade exposed via CLI for meta decisions."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or load_ai_config()
        self.selector = ModelSelector(self.config)
        self.drift_analyzer = DriftAnalyzer(self.config)
        self.explainer = ForecastExplainer(self.config, self.selector.provider_registry)

    def select_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.selector.select_model(context)
        return decision

    def summarize_drift(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ref_stats = context.get("reference_stats") or {}
        cur_stats = context.get("current_stats") or {}
        summary = self.drift_analyzer.drift_summary(ref_stats, cur_stats)
        return summary

    def explain_forecast(self, context: Dict[str, Any]) -> str:
        explanation = self.explainer.explain_forecast(context)
        return explanation


def _load_context(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI Orchestrator CLI")
    parser.add_argument("--ctx", type=Path, required=True, help="Path to context JSON.")
    parser.add_argument("--decide", action="store_true", help="Run model selection.")
    parser.add_argument("--drift", action="store_true", help="Summarize drift.")
    parser.add_argument("--explain", action="store_true", help="Generate forecast explanation.")
    args = parser.parse_args(argv)

    context = _load_context(args.ctx)
    orchestrator = AIOrchestrator()

    if args.decide:
        decision = orchestrator.select_model(context)
        print(json.dumps(decision, indent=2))
    if args.drift:
        summary = orchestrator.summarize_drift(context)
        print(json.dumps(summary, indent=2))
    if args.explain:
        markdown = orchestrator.explain_forecast(context)
        print(markdown)

    if not any([args.decide, args.drift, args.explain]):
        parser.error("Specify at least one action: --decide/--drift/--explain")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
