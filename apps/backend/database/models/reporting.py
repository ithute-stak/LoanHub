from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID as PythonUUID

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    scope_type = Column(String(20), nullable=False, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(String(180), nullable=False)
    report_type = Column(String(50), nullable=False, default="operations", index=True)
    frequency = Column(String(20), nullable=False, index=True)
    output_format = Column(String(10), nullable=False, default="pdf")
    recipients = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    next_run_at = Column(DateTime, nullable=False, index=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(30), nullable=True)
    last_error = Column(Text, nullable=True)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    reference = Column(String(50), nullable=False, unique=True, index=True)
    scope_type = Column(String(20), nullable=False, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("report_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("managed_files.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(String(240), nullable=False)
    report_type = Column(String(50), nullable=False, index=True)
    output_format = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="completed", index=True)
    metrics = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=False)

    file = relationship("ManagedFile")
    schedule = relationship("ReportSchedule")


def _json_safe(value):
    """Normalize report snapshots before PostgreSQL JSONB serialization.

    Management reports routinely aggregate Decimal currency values and date/UUID
    identifiers. Keeping the normalization at the report persistence boundary
    prevents callers from weakening their financial calculations just to satisfy
    the JSON encoder.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, PythonUUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _normalize_generated_report_metrics(_mapper, _connection, target: GeneratedReport) -> None:
    target.metrics = _json_safe(target.metrics or {})


event.listen(GeneratedReport, "before_insert", _normalize_generated_report_metrics)
event.listen(GeneratedReport, "before_update", _normalize_generated_report_metrics)
