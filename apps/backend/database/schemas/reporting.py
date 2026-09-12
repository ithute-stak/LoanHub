from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from database.schemas.file_management import ManagedFileRead


class ReportGenerateCreate(BaseModel):
    report_type: str = "operations"
    output_format: str = "pdf"
    scope_type: str = "company"
    company_id: UUID | None = None
    branch_id: UUID | None = None
    period_start: date
    period_end: date

    @field_validator("report_type")
    @classmethod
    def valid_report_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"operations", "financial", "portfolio", "performance", "compliance", "executive"}:
            raise ValueError("Invalid report type")
        return normalized

    @field_validator("output_format")
    @classmethod
    def valid_format(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"pdf", "csv"}:
            raise ValueError("Only PDF and CSV reports are supported")
        return normalized

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end < self.period_start:
            raise ValueError("Report end date cannot be before start date")
        return self


class ReportScheduleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    report_type: str = "operations"
    frequency: str
    output_format: str = "pdf"
    scope_type: str = "company"
    company_id: UUID | None = None
    branch_id: UUID | None = None
    recipients: list[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"daily", "weekly", "monthly", "annual"}:
            raise ValueError("Invalid report frequency")
        return normalized

    @field_validator("output_format")
    @classmethod
    def valid_format(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"pdf", "csv"}:
            raise ValueError("Only PDF and CSV reports are supported")
        return normalized


class ReportScheduleUpdate(BaseModel):
    name: str | None = None
    frequency: str | None = None
    report_type: str | None = None
    output_format: str | None = None
    recipients: list[str] | None = None
    is_active: bool | None = None


class ReportScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    name: str
    report_type: str
    frequency: str
    output_format: str
    recipients: list[str]
    is_active: bool
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime


class GeneratedReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    schedule_id: UUID | None = None
    title: str
    report_type: str
    output_format: str
    period_start: date
    period_end: date
    status: str
    metrics: dict
    generated_at: datetime
    file: ManagedFileRead | None = None


class ReportSummaryRead(BaseModel):
    scope_type: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    period_start: date
    period_end: date
    metrics: dict
