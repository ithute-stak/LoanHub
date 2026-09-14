from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasAnalysisRecord


_RAW_TEXT_KEYS = {"raw_text", "rawtext", "source_raw_text"}


def sanitize_analysis_snapshot(value: Any) -> Any:
    """Return JSON-safe structured analysis with pasted source text removed.

    This is deliberately recursive so a future analyzer cannot accidentally place
    raw clipboard content deeper in the structured snapshot and persist it.
    """
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalized in _RAW_TEXT_KEYS:
                continue
            cleaned[str(key)] = sanitize_analysis_snapshot(child)
        return cleaned
    if isinstance(value, list):
        return [sanitize_analysis_snapshot(child) for child in value]
    if isinstance(value, tuple):
        return [sanitize_analysis_snapshot(child) for child in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (date, Decimal, UUID)):
        return str(value)
    return str(value)


def analysis_fingerprint(
    analysis: dict[str, Any],
    *,
    client_name: str | None = None,
    client_reference: str | None = None,
) -> str:
    """Stable per-company duplicate key for one exact structured analysis."""
    payload = {
        "analysis": sanitize_analysis_snapshot(analysis),
        "client_name": (client_name or "").strip(),
        "client_reference": (client_reference or "").strip(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date_or_none(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _effective_client_identity(
    analysis: dict[str, Any],
    client_name: str | None,
    client_reference: str | None,
) -> tuple[str | None, str | None]:
    profile = analysis.get("profile") or {}
    name = (client_name or profile.get("full_name") or "").strip() or None
    reference = (
        client_reference
        or profile.get("employee_no")
        or profile.get("nid")
        or ""
    )
    reference = str(reference).strip() or None
    return name, reference


def _record_values(
    *,
    company_id: UUID,
    analyzed_by_user_id: UUID | None,
    analyzed_by_name: str | None,
    analyzed_by_role: str | None,
    client_name: str | None,
    client_reference: str | None,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    snapshot = sanitize_analysis_snapshot(analysis)
    effective_name, effective_reference = _effective_client_identity(
        snapshot,
        client_name,
        client_reference,
    )
    profile = snapshot.get("profile") or {}
    application = snapshot.get("application_context") or {}
    capacity = snapshot.get("capacity") or {}
    booking_term = snapshot.get("booking_term") or {}

    assessed = capacity.get("assessed_available_amount")
    if assessed is None:
        assessed = capacity.get("max_available_after_selected_deductions")
    if assessed is None:
        assessed = capacity.get("max_available_deduction_amount")

    return {
        "company_id": company_id,
        "analyzed_by_user_id": analyzed_by_user_id,
        "analyzed_by_name": (analyzed_by_name or "").strip() or None,
        "analyzed_by_role": (analyzed_by_role or "").strip() or None,
        "client_name": effective_name,
        "client_reference": effective_reference,
        "employee_no": str(profile.get("employee_no") or "").strip() or None,
        "nid": str(profile.get("nid") or "").strip() or None,
        "employer": str(profile.get("employer") or "").strip() or None,
        "current_agency_code": str(
            application.get("current_cdas_agency_code")
            or application.get("new_deduction_agency_code")
            or ""
        ).strip() or None,
        "current_agency_name": str(
            application.get("current_cdas_agency_name")
            or application.get("new_deduction_agency_name")
            or ""
        ).strip() or None,
        "decision": str(snapshot.get("decision") or "REVIEW_REQUIRED").strip().upper(),
        "assessed_available_amount": _decimal_or_none(assessed),
        "amount_owing": _decimal_or_none(booking_term.get("amount_owing")),
        "booking_months": int(booking_term["months_required"]) if booking_term.get("months_required") is not None else None,
        "next_possible_booking_date": _date_or_none(snapshot.get("next_possible_booking_date")),
        "reported_active_monthly_deductions": _decimal_or_none(snapshot.get("reported_active_monthly_deductions")) or Decimal("0"),
        "total_monthly_deductions": _decimal_or_none(snapshot.get("total_monthly_deductions")) or Decimal("0"),
        "data_quality_issue_count": int(snapshot.get("data_quality_issue_count") or 0),
        "analysis_fingerprint": analysis_fingerprint(
            snapshot,
            client_name=effective_name,
            client_reference=effective_reference,
        ),
        "analysis_snapshot": snapshot,
    }


def save_or_get_analysis_record(
    db: Session,
    *,
    company_id: UUID,
    analyzed_by_user_id: UUID | None,
    analyzed_by_name: str | None,
    analyzed_by_role: str | None,
    client_name: str | None,
    client_reference: str | None,
    analysis: dict[str, Any],
) -> tuple[CdasAnalysisRecord, bool]:
    """Persist one distinct analysis and return (record, created)."""
    values = _record_values(
        company_id=company_id,
        analyzed_by_user_id=analyzed_by_user_id,
        analyzed_by_name=analyzed_by_name,
        analyzed_by_role=analyzed_by_role,
        client_name=client_name,
        client_reference=client_reference,
        analysis=analysis,
    )
    fingerprint = values["analysis_fingerprint"]
    existing = db.query(CdasAnalysisRecord).filter(
        CdasAnalysisRecord.company_id == company_id,
        CdasAnalysisRecord.analysis_fingerprint == fingerprint,
    ).first()
    if existing:
        return existing, False

    record = CdasAnalysisRecord(**values)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(CdasAnalysisRecord).filter(
            CdasAnalysisRecord.company_id == company_id,
            CdasAnalysisRecord.analysis_fingerprint == fingerprint,
        ).first()
        if existing:
            return existing, False
        raise
    db.refresh(record)
    return record, True


def serialize_analysis_record(record: CdasAnalysisRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "client_name": record.client_name,
        "client_reference": record.client_reference,
        "employee_no": record.employee_no,
        "nid": record.nid,
        "employer": record.employer,
        "current_agency_code": record.current_agency_code,
        "current_agency_name": record.current_agency_name,
        "decision": record.decision,
        "assessed_available_amount": float(record.assessed_available_amount) if record.assessed_available_amount is not None else None,
        "amount_owing": float(record.amount_owing) if record.amount_owing is not None else None,
        "booking_months": record.booking_months,
        "next_possible_booking_date": record.next_possible_booking_date.isoformat() if record.next_possible_booking_date else None,
        "reported_active_monthly_deductions": float(record.reported_active_monthly_deductions or 0),
        "total_monthly_deductions": float(record.total_monthly_deductions or 0),
        "data_quality_issue_count": int(record.data_quality_issue_count or 0),
        "analyzed_by_name": record.analyzed_by_name,
        "analyzed_by_role": record.analyzed_by_role,
        "analyzed_at": record.created_at.isoformat() if record.created_at else None,
    }
