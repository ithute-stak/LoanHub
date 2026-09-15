from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasAnalysisRecord, CdasBookingOpportunity
from database.models.company_staff import CompanyStaff
from database.session import get_db
from services.cdas_advanced_search import (
    build_search_options,
    enrich_opportunity,
    filter_analyses,
    filter_opportunities,
)
from services.cdas_analysis_history import serialize_analysis_record
from services.cdas_booking_monitor import serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Advanced Search"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _staff_payload(row: CompanyStaff) -> dict:
    user = row.user
    person = getattr(user, "person", None) if user else None
    name = str(getattr(person, "full_name", "") or "").strip()
    if not name and user:
        name = str(user.email or user.phone or "").strip()
    return {
        "user_id": str(row.user_id),
        "name": name or "Company staff",
        "role": getattr(row.role, "value", str(row.role)),
        "is_active": bool(row.is_active),
    }


def _opportunity_summary(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "analysis_snapshot"}


@router.get("/advanced-search")
def advanced_cdas_search(
    q: str | None = Query(default=None, max_length=200),
    employer: str | None = Query(default=None, max_length=255),
    agency: str | None = Query(default=None, max_length=255),
    decision: str | None = Query(default=None, max_length=40),
    state: str | None = Query(default=None, max_length=40),
    pipeline_stage: str | None = Query(default=None, max_length=50),
    assigned_to_user_id: str | None = Query(default=None, max_length=50),
    quality: str | None = Query(default=None, pattern="^(all|clean|issues)$"),
    booking_from: date | None = None,
    booking_to: date | None = None,
    analyzed_from: date | None = None,
    analyzed_to: date | None = None,
    min_capacity: float | None = Query(default=None),
    max_capacity: float | None = Query(default=None),
    min_deduction: float | None = Query(default=None, ge=0),
    max_deduction: float | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Search archived CDAS analyses and live booking workflow using transparent filters."""
    _require_company_member(context)
    if booking_from and booking_to and booking_from > booking_to:
        raise HTTPException(status_code=422, detail="booking_from cannot be after booking_to")
    if analyzed_from and analyzed_to and analyzed_from > analyzed_to:
        raise HTTPException(status_code=422, detail="analyzed_from cannot be after analyzed_to")
    if min_capacity is not None and max_capacity is not None and min_capacity > max_capacity:
        raise HTTPException(status_code=422, detail="min_capacity cannot exceed max_capacity")
    if min_deduction is not None and max_deduction is not None and min_deduction > max_deduction:
        raise HTTPException(status_code=422, detail="min_deduction cannot exceed max_deduction")

    analysis_rows = db.query(CdasAnalysisRecord).filter(
        CdasAnalysisRecord.company_id == context.company_id
    ).order_by(CdasAnalysisRecord.created_at.desc(), CdasAnalysisRecord.id.desc()).all()
    analyses = [serialize_analysis_record(row) for row in analysis_rows]

    staff_rows = db.query(CompanyStaff).filter(
        CompanyStaff.company_id == context.company_id
    ).order_by(CompanyStaff.is_active.desc(), CompanyStaff.created_at.asc()).all()
    officers = [_staff_payload(row) for row in staff_rows]
    officer_names = {item["user_id"]: item["name"] for item in officers}

    opportunity_rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(CdasBookingOpportunity.created_at.desc(), CdasBookingOpportunity.id.desc()).all()
    serialized = []
    for row in opportunity_rows:
        item = serialize_opportunity(row)
        item["assigned_to_user_id"] = str(row.assigned_to_user_id) if row.assigned_to_user_id else None
        serialized.append(item)
    opportunities = dedupe_serialized_opportunities(serialized)
    opportunities = [
        enrich_opportunity(
            item,
            assigned_name=officer_names.get(str(item.get("assigned_to_user_id") or "")),
        )
        for item in opportunities
    ]

    common = {
        "query": q,
        "employer": employer,
        "agency": agency,
        "decision": decision,
        "quality": quality,
        "booking_from": booking_from,
        "booking_to": booking_to,
        "min_capacity": min_capacity,
        "max_capacity": max_capacity,
    }
    matching_analyses = filter_analyses(
        analyses,
        **common,
        analyzed_from=analyzed_from,
        analyzed_to=analyzed_to,
    )
    matching_opportunities = filter_opportunities(
        opportunities,
        **common,
        state=state,
        pipeline_stage=pipeline_stage,
        assigned_to_user_id=assigned_to_user_id,
        min_deduction=min_deduction,
        max_deduction=max_deduction,
    )

    return {
        "summary": {
            "analysis_total": len(analyses),
            "analysis_matches": len(matching_analyses),
            "opportunity_total": len(opportunities),
            "opportunity_matches": len(matching_opportunities),
        },
        "analyses": matching_analyses[:limit],
        "opportunities": [_opportunity_summary(item) for item in matching_opportunities[:limit]],
        "truncated": {
            "analyses": len(matching_analyses) > limit,
            "opportunities": len(matching_opportunities) > limit,
        },
        "options": build_search_options(analyses, opportunities, officers),
    }
