from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity, CdasOpportunityContact
from database.models.company_staff import CompanyStaff
from database.session import get_db
from services.cdas_booking_monitor import serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities
from services.cdas_contact_followups import (
    build_follow_up_workspace,
    normalize_channel,
    normalize_outcome,
    serialize_contact,
)

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Contact Follow-ups"])


class CdasContactCreateRequest(BaseModel):
    channel: str
    outcome: str
    notes: str | None = Field(default=None, max_length=4000)
    contacted_at: datetime | None = None
    next_follow_up_at: datetime | None = None


class CdasAssignmentRequest(BaseModel):
    user_id: UUID | None = None


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).replace(tzinfo=None)


def _company_opportunity(db: Session, *, opportunity_id: UUID, company_id: UUID) -> CdasBookingOpportunity:
    item = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.id == opportunity_id,
        CdasBookingOpportunity.company_id == company_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="CDAS booking opportunity not found")
    return item


def _staff_payload(row: CompanyStaff) -> dict:
    user = row.user
    person = getattr(user, "person", None) if user else None
    name = str(getattr(person, "full_name", "") or "").strip()
    if not name and user:
        name = str(user.email or user.phone or "").strip()
    return {
        "user_id": str(row.user_id),
        "name": name or "Company staff",
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "role": getattr(row.role, "value", str(row.role)),
    }


@router.get("/follow-ups")
def get_cdas_follow_up_workspace(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.created_at.desc()).all()
    values = []
    for row in rows:
        item = serialize_opportunity(row)
        item["assigned_to_user_id"] = str(row.assigned_to_user_id) if row.assigned_to_user_id else None
        values.append(item)
    values = dedupe_serialized_opportunities(values)

    contacts = db.query(CdasOpportunityContact).filter(
        CdasOpportunityContact.company_id == context.company_id
    ).order_by(CdasOpportunityContact.contacted_at.desc()).all()
    workspace = build_follow_up_workspace(values, contacts, now=_now())

    staff = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == context.company_id,
        CompanyStaff.is_active.is_(True),
    ).order_by(CompanyStaff.created_at.asc()).all()
    workspace["staff"] = [_staff_payload(row) for row in staff]
    return workspace


@router.post("/opportunities/{opportunity_id}/contacts")
def add_cdas_opportunity_contact(
    opportunity_id: UUID,
    payload: CdasContactCreateRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    item = _company_opportunity(db, opportunity_id=opportunity_id, company_id=context.company_id)
    try:
        channel = normalize_channel(payload.channel)
        outcome = normalize_outcome(payload.outcome)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    contacted_at = payload.contacted_at or _now()
    if payload.next_follow_up_at and payload.next_follow_up_at < contacted_at:
        raise HTTPException(status_code=422, detail="Next follow-up cannot be before the contact time")

    row = CdasOpportunityContact(
        company_id=context.company_id,
        opportunity_id=item.id,
        channel=channel,
        outcome=outcome,
        notes=(payload.notes or "").strip() or None,
        contacted_at=contacted_at,
        next_follow_up_at=payload.next_follow_up_at,
        created_by_user_id=context.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_contact(row)


@router.get("/opportunities/{opportunity_id}/contacts")
def list_cdas_opportunity_contacts(
    opportunity_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    _company_opportunity(db, opportunity_id=opportunity_id, company_id=context.company_id)
    rows = db.query(CdasOpportunityContact).filter(
        CdasOpportunityContact.company_id == context.company_id,
        CdasOpportunityContact.opportunity_id == opportunity_id,
    ).order_by(CdasOpportunityContact.contacted_at.desc()).all()
    return {"items": [serialize_contact(row) for row in rows], "total": len(rows)}


@router.patch("/opportunities/{opportunity_id}/assignment")
def assign_cdas_opportunity(
    opportunity_id: UUID,
    payload: CdasAssignmentRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_member(context)
    item = _company_opportunity(db, opportunity_id=opportunity_id, company_id=context.company_id)

    if payload.user_id is not None:
        staff = db.query(CompanyStaff).filter(
            CompanyStaff.company_id == context.company_id,
            CompanyStaff.user_id == payload.user_id,
            CompanyStaff.is_active.is_(True),
        ).first()
        if not staff:
            raise HTTPException(status_code=422, detail="Assigned officer must be active staff in this company")

    item.assigned_to_user_id = payload.user_id
    db.commit()
    db.refresh(item)
    return {
        "opportunity_id": str(item.id),
        "assigned_to_user_id": str(item.assigned_to_user_id) if item.assigned_to_user_id else None,
    }
