"""Pydantic models for UI API responses."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SeriesPoint(BaseModel):
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    value: Optional[float] = Field(None, description="Numeric value (NaN represented as null)")


class SeriesPayload(BaseModel):
    name: str
    unit: str = ""
    color: Optional[str] = None
    data: List[SeriesPoint] = Field(default_factory=list)


class SeriesResponse(BaseModel):
    series: List[SeriesPayload]
    meta: dict = Field(default_factory=dict)


class MetricRow(BaseModel):
    metric: str
    value: Optional[float]
    unit: str = ""


class MetricTable(BaseModel):
    rows: List[MetricRow] = Field(default_factory=list)
