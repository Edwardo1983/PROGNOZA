"""Prompt templates for LLM assisted orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


def _format_list(items: Iterable[str] | None) -> str:
    if not items:
        return "none"
    return ", ".join(str(item) for item in items)


@dataclass
class PromptTemplate:
    system: str
    user: str

    def render(self, **kwargs) -> Dict[str, str]:
        ctx = dict(kwargs)
        ctx.setdefault("quality_flags", [])
        ctx.setdefault("top_features", [])
        ctx.setdefault("data_quality", [])
        return {
            "system": self.system.format(**ctx).strip(),
            "user": self.user.format(
                **ctx,
                quality_list=_format_list(ctx.get("quality_flags")),
                top_features_list=_format_list(ctx.get("top_features")),
                data_quality_list=_format_list(ctx.get("data_quality")),
            ).strip(),
        }


MODEL_SELECTION_PROMPT = PromptTemplate(
    system="You are an expert PV forecasting operator. Be concise and pick the most reliable model.",
    user="""
Context:
- Intraday MAPE: {intraday_mape}%
- Day-ahead MAPE: {dayahead_mape}%
- Weather regime: {weather_regime}
- Data quality issues: {quality_list}

Available models:
1. physics  – deterministic, robust under extremes.
2. ml_xgb   – best when ample recent data, can overfit noisy inputs.
3. hybrid_blend – combines physics + ML, favours stability.

Select the single best option and provide a 1 sentence justification.
Return JSON: {{\"choice\": \"...\", \"rationale\": \"...\"}}
""",
)


DRIFT_NARRATIVE_PROMPT = PromptTemplate(
    system="You are a data quality analyst writing succinct drift summaries.",
    user="""
Recent monitoring comparison results:
- Drift score: {drift_score}
- Top features with drift: {top_features_list}
- Notes: {notes}

Draft 2 short sentences explaining whether drift is acceptable and next steps.
Return plain Markdown (no JSON).
""",
)


EXPLAIN_FORECAST_PROMPT = PromptTemplate(
    system="You explain PV forecast results to grid operators in concise Markdown.",
    user="""
Forecast run context:
- Site: {site_name}
- Generation window: {window}
- Selected model: {model}
- Expected MAPE: {expected_mape}%
- Weather regime: {weather_regime}
- Key metrics: {metrics}
- Uncertainty band: {uncertainty_band}
- Data quality notes: {data_quality_list}

Craft a short Markdown section with:
1. Summary bullet of forecast confidence.
2. Weather drivers.
3. Recommended operator action if uncertainty high.
""",
)
