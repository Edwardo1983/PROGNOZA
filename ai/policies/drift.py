from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..prompts import DRIFT_NARRATIVE_PROMPT
from ..providers.gpt import GPTProvider
from ..providers.claude import ClaudeProvider

logger = logging.getLogger(__name__)


def _population_stability_index(ref: np.ndarray, cur: np.ndarray, bins: int = 10) -> float:
    if len(ref) == 0 or len(cur) == 0:
        return 0.0
    quantiles = np.linspace(0, 1, bins + 1)
    cuts = np.quantile(ref, quantiles)
    cuts[0], cuts[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(ref, bins=cuts)
    cur_counts, _ = np.histogram(cur, bins=cuts)
    ref_dist = ref_counts / ref_counts.sum() if ref_counts.sum() else np.ones_like(ref_counts) / len(ref_counts)
    cur_dist = cur_counts / cur_counts.sum() if cur_counts.sum() else np.ones_like(cur_counts) / len(cur_counts)
    with np.errstate(divide="ignore", invalid="ignore"):
        psi = np.nansum((cur_dist - ref_dist) * np.log((cur_dist + 1e-8) / (ref_dist + 1e-8)))
    return float(max(psi, 0.0))


def _kolmogorov_smirnov(ref: np.ndarray, cur: np.ndarray) -> float:
    if len(ref) == 0 or len(cur) == 0:
        return 0.0
    ref_sorted = np.sort(ref)
    cur_sorted = np.sort(cur)
    all_values = np.concatenate([ref_sorted, cur_sorted])
    ref_cdf = np.searchsorted(ref_sorted, all_values, side="right") / len(ref_sorted)
    cur_cdf = np.searchsorted(cur_sorted, all_values, side="right") / len(cur_sorted)
    return float(np.max(np.abs(ref_cdf - cur_cdf)))


class DriftAnalyzer:
    """Compute drift metrics and optional LLM narrative."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        provider_cfg = cfg.get("providers", {})
        self.providers = {
            "openai": GPTProvider(provider_cfg.get("openai")),
            "anthropic": ClaudeProvider(provider_cfg.get("anthropic")),
        }
        self.temperature = cfg.get("llm", {}).get("temperature", 0.3)

    def drift_summary(self, ref_stats: Dict[str, Any], cur_stats: Dict[str, Any]) -> Dict[str, Any]:
        ref_df = pd.DataFrame(ref_stats)
        cur_df = pd.DataFrame(cur_stats)
        if ref_df.empty or cur_df.empty:
            return {"drift_score": 0.0, "top_features": [], "narrative_md": "No data available for drift analysis."}

        features = sorted(set(ref_df.columns).intersection(cur_df.columns))
        psi_scores: List[Tuple[str, float]] = []
        ks_scores: List[Tuple[str, float]] = []
        for feature in features:
            ref_vals = pd.to_numeric(ref_df[feature], errors="coerce").dropna().to_numpy()
            cur_vals = pd.to_numeric(cur_df[feature], errors="coerce").dropna().to_numpy()
            if len(ref_vals) == 0 or len(cur_vals) == 0:
                continue
            psi = _population_stability_index(ref_vals, cur_vals)
            ks = _kolmogorov_smirnov(ref_vals, cur_vals)
            psi_scores.append((feature, psi))
            ks_scores.append((feature, ks))

        combined = {}
        for feature, psi in psi_scores:
            combined.setdefault(feature, {})["psi"] = psi
        for feature, ks in ks_scores:
            combined.setdefault(feature, {})["ks"] = ks

        drift_score = float(np.mean([vals.get("psi", 0.0) for vals in combined.values()]) if combined else 0.0)
        top_features = sorted(combined.items(), key=lambda kv: max(kv[1].values()), reverse=True)[:3]
        top_feature_names = [name for name, _ in top_features]

        narrative = self._narrative(
            drift_score,
            top_feature_names,
            notes=ref_stats.get("notes") or cur_stats.get("notes"),
        )
        return {
            "drift_score": drift_score,
            "top_features": [
                {"feature": name, **metrics} for name, metrics in top_features
            ],
            "narrative_md": narrative,
        }

    def _narrative(self, drift_score: float, top_features: List[str], notes: Optional[str]) -> str:
        provider = next((p for p in self.providers.values() if p.is_available()), None)
        if not provider:
            status = "low" if drift_score < 0.1 else "moderate" if drift_score < 0.25 else "high"
            feature_text = ", ".join(top_features) if top_features else "no features"
            return f"Drift level is {status} (score {drift_score:.2f}); top drivers: {feature_text}."

        render = DRIFT_NARRATIVE_PROMPT.render(
            drift_score=f"{drift_score:.2f}",
            top_features=top_features,
            notes=notes,
        )
        try:
            return provider.chat(render["system"], render["user"], temperature=self.temperature)
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM drift narrative failed (%s)", exc)
            feature_text = ", ".join(top_features) if top_features else "no features"
            return f"Drift score {drift_score:.2f}; key drivers: {feature_text}."
