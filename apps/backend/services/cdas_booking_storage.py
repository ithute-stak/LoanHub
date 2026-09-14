from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingOpportunity
from services.cdas_booking_monitor import local_today


def _normalise_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _preferred_serialized_record(current: dict, candidate: dict) -> dict:
    current_score = (
        1 if current.get("state") == "BOOKED" else 0,
        1 if current.get("client_name") else 0,
        1 if current.get("client_reference") else 0,
    )
    candidate_score = (
        1 if candidate.get("state") == "BOOKED" else 0,
        1 if candidate.get("client_name") else 0,
        1 if candidate.get("client_reference") else 0,
    )
    return candidate if candidate_score > current_score else current


def serialized_opportunity_identity(item: dict) -> str:
    reference = _normalise_text(item.get("opportunity_reference_no"))
    item_code = _normalise_text(item.get("opportunity_item_code"))
    if reference:
        return f"reference:{item_code}:{reference}" if item_code else f"reference:{reference}"

    client_reference = _normalise_text(item.get("client_reference"))
    expiry = str(item.get("opportunity_expiry_date") or "")[:10]
    if client_reference and item_code:
        return f"client-item:{client_reference}:{item_code}:{expiry}"

    return f"id:{item.get('id')}"


def dedupe_serialized_opportunities(items: list[dict]) -> list[dict]:
    """Collapse duplicate cards without deleting legacy rows from production."""
    selected: dict[str, dict] = {}
    order: list[str] = []
    for item in items:
        key = serialized_opportunity_identity(item)
        if key not in selected:
            selected[key] = item
            order.append(key)
            continue
        selected[key] = _preferred_serialized_record(selected[key], item)
    return [selected[key] for key in order]


def _find_existing(
    db: Session,
    *,
    company_id,
    reference_no: str | None,
    client_reference: str | None,
    item_code: str | None,
    expiry_date: date | None,
) -> CdasBookingOpportunity | None:
    query = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == company_id
    )

    if reference_no:
        reference_query = query.filter(
            CdasBookingOpportunity.opportunity_reference_no == reference_no
        )
        if item_code:
            reference_query = reference_query.filter(
                CdasBookingOpportunity.opportunity_item_code == item_code
            )
        candidates = reference_query.order_by(
            CdasBookingOpportunity.created_at.asc()
        ).all()
    elif client_reference and item_code:
        candidates = query.filter(
            CdasBookingOpportunity.client_reference == client_reference,
            CdasBookingOpportunity.opportunity_item_code == item_code,
            CdasBookingOpportunity.opportunity_expiry_date == expiry_date,
        ).order_by(CdasBookingOpportunity.created_at.asc()).all()
    else:
        candidates = []

    if not candidates:
        return None

    booked = next((item for item in candidates if item.status == "booked"), None)
    named = next((item for item in candidates if item.client_name), None)
    return booked or named or candidates[0]


def save_or_update_opportunity_from_analysis(
    db: Session,
    *,
    company_id,
    client_name: str | None,
    client_reference: str | None,
    alert_lead_days: int,
    analysis: dict,
) -> CdasBookingOpportunity:
    """Upsert a CDAS opportunity using a stable reference before inserting a new row."""
    row = analysis.get("opportunity") or (analysis.get("own_bookings") or [None])[0]
    profile = analysis.get("profile") or {}
    derived_name = (profile.get("full_name") or "").strip() or None
    derived_reference = str(
        profile.get("employee_no") or profile.get("nid") or ""
    ).strip() or None

    effective_name = (client_name or derived_name or "").strip() or None
    effective_reference = (client_reference or derived_reference or "").strip() or None
    row_reference = (row.get("reference_no") or "").strip() if row else None
    row_item_code = (row.get("item_code") or "").strip() if row else None
    row_expiry = _parse_iso_date(row.get("expiry_date")) if row else None

    booking_open = None
    if analysis.get("next_possible_booking_date"):
        booking_open = _parse_iso_date(analysis.get("next_possible_booking_date"))
    elif row and row.get("booking_open_date"):
        booking_open = _parse_iso_date(row.get("booking_open_date"))
    if analysis.get("decision") == "BOOK_NOW" and booking_open is None:
        booking_open = local_today()

    alert_start = booking_open - timedelta(days=alert_lead_days) if booking_open else None
    analysis_says_booked = analysis.get("decision") == "ALREADY_BOOKED"

    item = _find_existing(
        db,
        company_id=company_id,
        reference_no=row_reference,
        client_reference=effective_reference,
        item_code=row_item_code,
        expiry_date=row_expiry,
    )
    if item is None:
        item = CdasBookingOpportunity(company_id=company_id)
        db.add(item)

    preserve_booked = item.status == "booked"
    item.client_name = effective_name or item.client_name
    item.client_reference = effective_reference or item.client_reference
    item.status = "booked" if analysis_says_booked or preserve_booked else "monitoring"
    item.booking_lead_months = int(analysis.get("booking_lead_months") or 0)
    item.alert_lead_days = alert_lead_days
    item.booking_open_date = booking_open
    item.alert_start_date = alert_start
    item.opportunity_agency_name = row.get("agency_name") if row else None
    item.opportunity_item_code = row_item_code
    item.opportunity_reference_no = row_reference
    item.opportunity_effective_date = _parse_iso_date(row.get("effective_date")) if row else None
    item.opportunity_expiry_date = row_expiry
    item.opportunity_deduction_amount = (
        Decimal(str(row.get("deduction_amount") or 0)) if row else None
    )
    item.total_monthly_deductions = Decimal(
        str(analysis.get("total_monthly_deductions") or 0)
    )
    item.own_monthly_deductions = Decimal(
        str(analysis.get("own_monthly_deductions") or 0)
    )
    item.competitor_monthly_deductions = Decimal(
        str(analysis.get("competitor_monthly_deductions") or 0)
    )
    item.analysis_snapshot = analysis
    if item.status == "booked" and item.booked_at is None:
        item.booked_at = datetime.utcnow()

    db.commit()
    db.refresh(item)
    return item
