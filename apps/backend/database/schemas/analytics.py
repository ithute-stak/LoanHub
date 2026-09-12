from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


MetricFormat = Literal["money", "integer", "percent", "decimal"]
InsightTone = Literal["positive", "warning", "critical", "neutral"]


class AnalyticsMetricRead(BaseModel):
    key: str
    label: str
    value: float
    format: MetricFormat = "decimal"
    previous_value: float | None = None
    change_percent: float | None = None
    description: str | None = None


class AnalyticsTimePointRead(BaseModel):
    period: str
    values: dict[str, float] = Field(default_factory=dict)


class AnalyticsBreakdownPointRead(BaseModel):
    label: str
    value: float
    count: int | None = None
    secondary_value: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalyticsScatterPointRead(BaseModel):
    label: str
    x: float
    y: float
    size: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalyticsHeatmapPointRead(BaseModel):
    day: str
    hour: int
    value: int


class AnalyticsInsightRead(BaseModel):
    title: str
    message: str
    tone: InsightTone = "neutral"
    action_url: str | None = None


class AnalyticsScopeRead(BaseModel):
    scope: Literal["platform", "company", "borrower"]
    company_id: str | None = None
    branch_id: str | None = None
    borrower_id: str | None = None
    role: str | None = None
    date_from: date
    date_to: date
    granularity: Literal["day", "week", "month"]


class AnalyticsDashboardRead(BaseModel):
    scope: AnalyticsScopeRead
    metrics: list[AnalyticsMetricRead] = Field(default_factory=list)
    series: dict[str, list[AnalyticsTimePointRead]] = Field(default_factory=dict)
    breakdowns: dict[str, list[AnalyticsBreakdownPointRead]] = Field(default_factory=dict)
    scatter: dict[str, list[AnalyticsScatterPointRead]] = Field(default_factory=dict)
    heatmaps: dict[str, list[AnalyticsHeatmapPointRead]] = Field(default_factory=dict)
    insights: list[AnalyticsInsightRead] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)
    generated_at: datetime
