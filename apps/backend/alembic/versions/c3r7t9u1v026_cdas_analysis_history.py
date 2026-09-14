"""Add persistent CDAS analysis history and backfill recoverable snapshots.

Revision ID: c3r7t9u1v026
Revises: b2r6t8u0v025
Create Date: 2026-09-14

This migration is additive. It does not alter or delete existing CDAS booking
opportunities. Existing structured opportunity snapshots are copied into the new
history table where possible so previously saved analyses become reportable from
the history view. Raw pasted CDAS text is removed recursively if ever present.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3r7t9u1v026"
down_revision = "b2r6t8u0v025"
branch_labels = None
depends_on = None


_RAW_TEXT_KEYS = {"raw_text", "rawtext", "source_raw_text"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalized in _RAW_TEXT_KEYS:
                continue
            cleaned[str(key)] = _sanitize(child)
        return cleaned
    if isinstance(value, list):
        return [_sanitize(child) for child in value]
    return value


def _fingerprint(analysis: dict[str, Any], client_name: str | None, client_reference: str | None) -> str:
    payload = {
        "analysis": _sanitize(analysis),
        "client_name": (client_name or "").strip(),
        "client_reference": (client_reference or "").strip(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def upgrade() -> None:
    op.create_table(
        "cdas_analysis_records",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analyzed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analyzed_by_name", sa.String(length=255), nullable=True),
        sa.Column("analyzed_by_role", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column("client_reference", sa.String(length=200), nullable=True),
        sa.Column("employee_no", sa.String(length=200), nullable=True),
        sa.Column("nid", sa.String(length=200), nullable=True),
        sa.Column("employer", sa.String(length=255), nullable=True),
        sa.Column("current_agency_code", sa.String(length=100), nullable=True),
        sa.Column("current_agency_name", sa.String(length=255), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("assessed_available_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount_owing", sa.Numeric(18, 2), nullable=True),
        sa.Column("booking_months", sa.Integer(), nullable=True),
        sa.Column("next_possible_booking_date", sa.Date(), nullable=True),
        sa.Column("reported_active_monthly_deductions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_monthly_deductions", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("data_quality_issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analysis_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("analysis_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analyzed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "analysis_fingerprint", name="uq_cdas_analysis_records_company_fingerprint"),
    )
    for column in (
        "company_id",
        "analyzed_by_user_id",
        "client_name",
        "client_reference",
        "decision",
        "next_possible_booking_date",
        "analysis_fingerprint",
    ):
        op.create_index(
            f"ix_cdas_analysis_records_{column}",
            "cdas_analysis_records",
            [column],
            unique=False,
        )

    # Backfill all recoverable historical analyses from the existing structured
    # opportunity snapshots. Existing opportunity rows remain untouched. Explicit
    # SQLAlchemy types are used here so PostgreSQL receives UUID/JSONB/date values
    # through the correct bind processors during a live migration.
    connection = op.get_bind()
    uuid_type = postgresql.UUID(as_uuid=True)
    json_type = postgresql.JSONB(astext_type=sa.Text())
    money_type = sa.Numeric(18, 2)
    source = sa.table(
        "cdas_booking_opportunities",
        sa.column("company_id", uuid_type),
        sa.column("client_name", sa.String(length=200)),
        sa.column("client_reference", sa.String(length=200)),
        sa.column("analysis_snapshot", json_type),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    target = sa.table(
        "cdas_analysis_records",
        sa.column("company_id", uuid_type),
        sa.column("client_name", sa.String(length=200)),
        sa.column("client_reference", sa.String(length=200)),
        sa.column("employee_no", sa.String(length=200)),
        sa.column("nid", sa.String(length=200)),
        sa.column("employer", sa.String(length=255)),
        sa.column("current_agency_code", sa.String(length=100)),
        sa.column("current_agency_name", sa.String(length=255)),
        sa.column("decision", sa.String(length=30)),
        sa.column("assessed_available_amount", money_type),
        sa.column("amount_owing", money_type),
        sa.column("booking_months", sa.Integer()),
        sa.column("next_possible_booking_date", sa.Date()),
        sa.column("reported_active_monthly_deductions", money_type),
        sa.column("total_monthly_deductions", money_type),
        sa.column("data_quality_issue_count", sa.Integer()),
        sa.column("analysis_fingerprint", sa.String(length=64)),
        sa.column("analysis_snapshot", json_type),
        sa.column("id", uuid_type),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    seen: set[tuple[Any, str]] = set()
    rows = connection.execute(
        sa.select(
            source.c.company_id,
            source.c.client_name,
            source.c.client_reference,
            source.c.analysis_snapshot,
            source.c.created_at,
            source.c.updated_at,
        ).where(source.c.analysis_snapshot.is_not(None))
    ).mappings()

    for row in rows:
        snapshot = _sanitize(row["analysis_snapshot"] or {})
        if not snapshot:
            continue
        profile = snapshot.get("profile") or {}
        application = snapshot.get("application_context") or {}
        capacity = snapshot.get("capacity") or {}
        booking_term = snapshot.get("booking_term") or {}
        client_name = str(row["client_name"] or profile.get("full_name") or "").strip() or None
        client_reference = str(
            row["client_reference"]
            or profile.get("employee_no")
            or profile.get("nid")
            or ""
        ).strip() or None
        fingerprint = _fingerprint(snapshot, client_name, client_reference)
        duplicate_key = (row["company_id"], fingerprint)
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)

        assessed = capacity.get("assessed_available_amount")
        if assessed is None:
            assessed = capacity.get("max_available_after_selected_deductions")
        if assessed is None:
            assessed = capacity.get("max_available_deduction_amount")

        months = booking_term.get("months_required")
        try:
            months = int(months) if months is not None else None
        except (TypeError, ValueError):
            months = None

        connection.execute(target.insert().values(
            company_id=row["company_id"],
            client_name=client_name,
            client_reference=client_reference,
            employee_no=str(profile.get("employee_no") or "").strip() or None,
            nid=str(profile.get("nid") or "").strip() or None,
            employer=str(profile.get("employer") or "").strip() or None,
            current_agency_code=str(
                application.get("current_cdas_agency_code")
                or application.get("new_deduction_agency_code")
                or ""
            ).strip() or None,
            current_agency_name=str(
                application.get("current_cdas_agency_name")
                or application.get("new_deduction_agency_name")
                or ""
            ).strip() or None,
            decision=str(snapshot.get("decision") or "REVIEW_REQUIRED").upper(),
            assessed_available_amount=_decimal(assessed),
            amount_owing=_decimal(booking_term.get("amount_owing")),
            booking_months=months,
            next_possible_booking_date=_date(snapshot.get("next_possible_booking_date")),
            reported_active_monthly_deductions=_decimal(snapshot.get("reported_active_monthly_deductions")) or Decimal("0"),
            total_monthly_deductions=_decimal(snapshot.get("total_monthly_deductions")) or Decimal("0"),
            data_quality_issue_count=int(snapshot.get("data_quality_issue_count") or 0),
            analysis_fingerprint=fingerprint,
            analysis_snapshot=snapshot,
            id=uuid.uuid4(),
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
        ))


def downgrade() -> None:
    op.drop_table("cdas_analysis_records")
