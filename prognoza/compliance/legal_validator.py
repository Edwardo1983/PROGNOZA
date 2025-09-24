"""Verificari de conformitate cu legislatia energetica romana."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

import pandas as pd

from prognoza.config.settings import DeadlineConfig, PREInfo, QualityThresholds
from prognoza.data_acquisition.data_validator import DataValidator
from prognoza.processing.notification_builder import PhysicalNotification
from prognoza.reporting.transelectrica_export import ensure_deadline


@dataclass(slots=True)
class ComplianceIssue:
    severity: str
    message: str


class LegalValidator:
    """Executa verificari de conformitate legala."""

    def __init__(self, pre: PREInfo, thresholds: QualityThresholds, deadlines: DeadlineConfig) -> None:
        self._pre = pre
        self._thresholds = thresholds
        self._deadlines = deadlines
        self._quality_validator = DataValidator(thresholds)

    def validate_notification(self, notification: PhysicalNotification) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        expected_intervals = 96 if notification.resolution == "15min" else 24
        if len(notification.intervals) != expected_intervals:
            issues.append(
                ComplianceIssue(
                    severity="high",
                    message="Numar intervale invalid pentru notificare fizica",
                )
            )
        for entry in notification.intervals:
            if entry.power_mw < 0:
                issues.append(
                    ComplianceIssue(
                        severity="high",
                        message=f"Putere negativa detectata {entry.power_mw:.3f} MW",
                    )
                )
        return issues

    def validate_deadline(self, delivery_day: datetime, submit_time: datetime) -> List[ComplianceIssue]:
        if not ensure_deadline(delivery_day, submit_time, self._pre.timezone):
            return [
                ComplianceIssue(
                    severity="high",
                    message="Transmitere dupa termenul D-1 ora 15:00 (Cod RET cap. 6.5.2)",
                )
            ]
        return []

    def validate_quality(self, measurements: pd.DataFrame) -> List[ComplianceIssue]:
        result = self._quality_validator.validate_quality(measurements)
        return [ComplianceIssue(severity="medium", message=issue) for issue in result.issues]

    def validate_completeness(self, measurements: pd.DataFrame, frequency_minutes: int) -> List[ComplianceIssue]:
        result = self._quality_validator.validate_completeness(measurements, frequency_minutes)
        if result.passed:
            return []
        return [ComplianceIssue(severity="high", message=issue) for issue in result.issues]

    def run_all(
        self,
        notification: PhysicalNotification,
        production_profile: pd.DataFrame,
        submit_time: datetime,
    ) -> List[ComplianceIssue]:
        issues: List[ComplianceIssue] = []
        issues.extend(self.validate_notification(notification))
        issues.extend(self.validate_deadline(notification.delivery_day, submit_time))
        issues.extend(self.validate_completeness(production_profile, 15))
        issues.extend(self.validate_quality(production_profile))
        return issues
