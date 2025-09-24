"""Definirea task-urilor planificate ale sistemului."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from prognoza.compliance.audit_trail import AuditTrail
from prognoza.compliance.deadline_monitor import DeadlineMonitor
from prognoza.compliance.legal_validator import LegalValidator
from prognoza.config.settings import Settings
from prognoza.data_acquisition.umg_reader import fetch_measurements
from prognoza.processing.aggregator import prepare_notification_series
from prognoza.processing.notification_builder import build_notification
from prognoza.reporting.transelectrica_export import save_csv, save_xml


class TaskRegistry:
    """Inregistreaza task-uri automate pentru conformitate legala."""

    def __init__(self, settings: Settings, monitor: DeadlineMonitor, validator: LegalValidator) -> None:
        self._settings = settings
        self._monitor = monitor
        self._validator = validator
        self._audit = AuditTrail(Path("logs"))

    def register_all(self) -> None:
        self._monitor.schedule_d_minus_one(self.generate_and_send_notification)
        self._monitor.schedule_monthly_anre(self.generate_anre_report)

    def start(self) -> None:
        self._monitor.start()

    def generate_and_send_notification(self) -> None:
        try:
            measurement = fetch_measurements(self._settings.modbus, http_config=self._settings.umg_http)
        except ConnectionError as exc:
            self._audit.record("umg_read_failed", {"error": str(exc)})
            return
        df = pd.DataFrame([measurement.values], index=[measurement.timestamp])
        profile = prepare_notification_series(df, datetime.now())
        notification = build_notification(self._settings.pre, profile["planned_mw"])
        issues = self._validator.validate_notification(notification)
        if issues:
            self._audit.record("notification_validation_failed", {"issues": [issue.message for issue in issues]})
            return
        export_dir = self._settings.storage.export_dir
        export_dir.mkdir(exist_ok=True, parents=True)
        timestamp = datetime.now()
        xml_path = export_dir / f"notificare_{timestamp:%Y%m%d}.xml"
        csv_path = export_dir / f"notificare_{timestamp:%Y%m%d}.csv"
        save_xml(notification, xml_path)
        save_csv(notification, csv_path, unit_id="UMG509")
        self._audit.record(
            "notification_generated",
            {"xml": str(xml_path), "csv": str(csv_path), "delivery_day": notification.delivery_day.isoformat()},
        )

    def generate_anre_report(self) -> None:
        from prognoza.reporting.anre_reports import generate_monthly_report

        export_dir = self._settings.storage.export_dir
        export_dir.mkdir(exist_ok=True, parents=True)
        month = datetime.now()
        data = {
            "energie_activa_produsa": 0.0,
            "energie_activa_livrata": 0.0,
            "energie_consum_propriu": 0.0,
            "energie_reactiva": 0.0,
            "disponibilitate_centrala": 100.0,
            "ore_functionare": 0,
        }
        incidents = pd.DataFrame(columns=["data", "durata_ore", "descriere", "impact"])
        output = export_dir / f"anre_{month:%Y_%m}.xlsx"
        generate_monthly_report(data, incidents, output, month)
        self._audit.record("anre_report_generated", {"file": str(output)})
