"""API REST pentru integrare cu dispeceratul PRE/BRP."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException

from prognoza.compliance.legal_validator import ComplianceIssue, LegalValidator
from prognoza.config.settings import Settings, load_settings
from prognoza.infrastructure.database import Measurement, NotificationLog, get_session, init_engine

app = FastAPI(title="Prognoza PV", version="1.0.0")

_settings: Settings | None = None
_engine = None
_validator: LegalValidator | None = None


def get_settings() -> Settings:
    global _settings, _engine, _validator
    if _settings is None:
        _settings = load_settings()
    if _engine is None:
        _engine = init_engine(_settings.storage.database_url)
    if _validator is None:
        _validator = LegalValidator(_settings.pre, _settings.quality, _settings.deadlines)
    return _settings


def get_validator(settings: Settings = Depends(get_settings)) -> LegalValidator:
    global _validator
    if _validator is None:
        _validator = LegalValidator(settings.pre, settings.quality, settings.deadlines)
    return _validator


def get_db(settings: Settings = Depends(get_settings)):
    global _engine
    if _engine is None:
        _engine = init_engine(settings.storage.database_url)
    return get_session(_engine)


@app.get("/status")
def status(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    return {
        "pre": settings.pre.cod_pre,
        "brp": settings.pre.cod_brp,
        "timezone": settings.pre.timezone,
    }


@app.get("/measurements", response_model=List[Dict[str, Any]])
def list_measurements(limit: int = 96, db=Depends(get_db)):
    with db as session:
        rows = (
            session.query(Measurement)
            .order_by(Measurement.timestamp.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "timestamp": row.timestamp.isoformat(),
            "active_power_kw": row.active_power_kw,
            "reactive_power_kvar": row.reactive_power_kvar,
            "energy_export_kwh": row.energy_export_kwh,
            "metadata": row.metadata_json,
        }
        for row in rows
    ]


@app.post("/notifications/validate")
def validate_notification(payload: Dict[str, Any], validator: LegalValidator = Depends(get_validator)) -> Dict[str, Any]:
    try:
        intervals = payload["intervals"]
        series = pd.Series({pd.Timestamp(interval["start"]): interval["power_mw"] for interval in intervals})
        target_tz = payload.get("timezone", "Europe/Bucharest")
        if series.index.tz is None:
            series.index = series.index.tz_localize(target_tz, nonexistent="shift_forward")
        else:
            series.index = series.index.tz_convert(target_tz)
        from prognoza.processing.notification_builder import PhysicalNotification, IntervalEntry

        notification = PhysicalNotification(
            cod_pre=payload["cod_pre"],
            cod_brp=payload["cod_brp"],
            delivery_day=pd.Timestamp(payload["delivery_day"]).to_pydatetime(),
            resolution=payload.get("resolution", "15min"),
            aggregated_mw=float(payload.get("aggregated_mw", 0.0)),
            intervals=[
                IntervalEntry(
                    start=pd.Timestamp(interval["start"]).to_pydatetime(),
                    end=pd.Timestamp(interval["end"]).to_pydatetime(),
                    power_mw=float(interval["power_mw"]),
                )
                for interval in intervals
            ],
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing key {exc}")
    issues: List[ComplianceIssue] = validator.validate_notification(notification)
    return {
        "issues": [issue.__dict__ for issue in issues],
        "passed": not issues,
    }


@app.post("/notifications/log")
def log_notification(record: Dict[str, Any], db=Depends(get_db)):
    required = {"delivery_day", "submitted_at", "transport_reference", "file_hash"}
    missing = required - record.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing keys: {missing}")
    with db as session:
        entry = NotificationLog(
            delivery_day=pd.Timestamp(record["delivery_day"]).to_pydatetime(),
            submitted_at=pd.Timestamp(record["submitted_at"]).to_pydatetime(),
            transport_reference=record["transport_reference"],
            file_hash=record["file_hash"],
        )
        session.add(entry)
    return {"status": "ok"}
