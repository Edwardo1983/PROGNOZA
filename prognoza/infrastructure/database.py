"""Persistenta datelor de productie si prognoza."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    active_power_kw: Mapped[float] = mapped_column(Float)
    reactive_power_kvar: Mapped[float] = mapped_column(Float)
    energy_export_kwh: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSON)


class QualityFlag(Base):
    __tablename__ = "quality_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measurement_id: Mapped[int] = mapped_column(Integer, index=True)
    issue: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(50))


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_day: Mapped[datetime] = mapped_column(DateTime, index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    mae: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)


class NotificationLog(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_day: Mapped[datetime] = mapped_column(DateTime, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    transport_reference: Mapped[str] = mapped_column(String(128))
    file_hash: Mapped[str] = mapped_column(String(128))


def init_engine(database_url: str):
    engine = create_engine(database_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def get_session(engine) -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
