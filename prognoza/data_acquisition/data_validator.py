"""Validarea datelor de masura conform standardelor SR EN 50160 si Cod RET."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from prognoza.config.settings import QualityThresholds


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    issues: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {"passed": self.passed, "issues": self.issues}


class DataValidator:
    """Aplica pragurile prevazute de reglementari asupra datelor de masura."""

    def __init__(self, thresholds: QualityThresholds) -> None:
        self._thresholds = thresholds

    def validate_quality(self, data: pd.DataFrame) -> ValidationResult:
        """Verifica THD, factor de putere si variatii tensiune.

        Args:
            data: DataFrame cu coloane `thd_voltage`, `thd_current`, `power_factor`,
                  `voltage_l1`, `voltage_l2`, `voltage_l3`.
        """
        issues: List[str] = []
        if "thd_voltage" in data:
            max_thd_v = data["thd_voltage"].max()
            if max_thd_v > self._thresholds.max_thd_voltage:
                issues.append(
                    f"THD tensiune {max_thd_v:.2f}% depaseste limita {self._thresholds.max_thd_voltage}%"
                )
        if "thd_current" in data:
            max_thd_i = data["thd_current"].max()
            if max_thd_i > self._thresholds.max_thd_current:
                issues.append(
                    f"THD curent {max_thd_i:.2f}% depaseste limita {self._thresholds.max_thd_current}%"
                )
        if "power_factor" in data:
            min_pf = data["power_factor"].min()
            if min_pf < self._thresholds.min_power_factor:
                issues.append(
                    f"Factorul de putere {min_pf:.2f} este sub pragul legal {self._thresholds.min_power_factor}"
                )
        voltage_cols = [col for col in data.columns if col.startswith("voltage_")]
        for col in voltage_cols:
            deviations = self._voltage_deviation(data[col])
            over_max = deviations[deviations > self._thresholds.voltage_max_percent]
            under_min = deviations[deviations < self._thresholds.voltage_min_percent]
            if not over_max.empty:
                issues.append(
                    f"{col} depaseste +{self._thresholds.voltage_max_percent}% pentru {len(over_max)} inregistrari"
                )
            if not under_min.empty:
                issues.append(
                    f"{col} scade sub {self._thresholds.voltage_min_percent}% pentru {len(under_min)} inregistrari"
                )
        return ValidationResult(passed=not issues, issues=issues)

    def validate_completeness(self, data: pd.DataFrame, expected_frequency_minutes: int) -> ValidationResult:
        """Verifica daca datele acopera toate intervalele cerute de PO TEL-133."""
        issues: List[str] = []
        if data.empty:
            issues.append("Setul de date este gol")
            return ValidationResult(False, issues)
        index = data.index
        if not isinstance(index, pd.DatetimeIndex):
            raise ValueError("DataFrame must be indexed by datetime for completeness check")
        index = index.sort_values()
        diffs = index.to_series().diff().dropna()
        gaps = diffs[diffs > pd.Timedelta(minutes=expected_frequency_minutes)]
        for ts, delta in gaps.items():
            issues.append(f"Lipsesc intervale: {delta} in jurul {ts}")
        return ValidationResult(passed=not issues, issues=issues)

    def _voltage_deviation(self, series: pd.Series) -> pd.Series:
        nominal = series.mean()
        if nominal == 0:
            return pd.Series([0], index=series.index)
        return (series - nominal) / nominal * 100


def summarize_results(results: Iterable[ValidationResult]) -> ValidationResult:
    issues: List[str] = []
    for result in results:
        issues.extend(result.issues)
    return ValidationResult(passed=not issues, issues=issues)
