from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasBookingOpportunity
from database.session import get_db
from services.cdas_booking_monitor import local_today, serialize_opportunity
from services.cdas_booking_storage import dedupe_serialized_opportunities
from services.cdas_opportunity_pipeline import (
    build_opportunity_pipeline,
    transition_pipeline_stage,
)

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Opportunity Pipeline"])


class CdasPipelineTransitionRequest(BaseModel):
    stage: str


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


def _company_opportunity(
    db: Session,
    *,
    opportunity_id: UUID,
    company_id: UUID,
) -> CdasBookingOpportunity:
    item = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.id == opportunity_id,
        CdasBookingOpportunity.company_id == company_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="CDAS booking opportunity not found")
    return item


@router.get("/pipeline")
def get_cdas_opportunity_pipeline(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the company's persistent CDAS opportunity workflow board."""
    _require_company_member(context)
    rows = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(
        CdasBookingOpportunity.booking_open_date.asc().nullslast(),
        CdasBookingOpportunity.created_at.desc(),
    ).all()
    values = dedupe_serialized_opportunities(
        [serialize_opportunity(item, today=local_today()) for item in rows]
    )
    return build_opportunity_pipeline(values)


@router.patch("/opportunities/{opportunity_id}/pipeline")
def update_cdas_opportunity_pipeline_stage(
    opportunity_id: UUID,
    payload: CdasPipelineTransitionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Move one company opportunity to another valid workflow stage."""
    _require_company_member(context)
    item = _company_opportunity(
        db,
        opportunity_id=opportunity_id,
        company_id=context.company_id,
    )
    try:
        item = transition_pipeline_stage(
            db,
            item=item,
            target_stage=payload.stage,
            user_id=context.user.id,
            allow_direct_booked=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_opportunity(item, today=local_today())
