from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.access_control import TenantContext, get_tenant_context
from database.config.config import settings
from services.cdas_booking_analyzer import analyse_cdas_booking


router = APIRouter(prefix="/cdas-booking", tags=["CDAS Booking Analyzer"])


class CdasBookingAnalyseRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=100_000)
    booking_lead_months: int = Field(default=6, ge=0, le=60)
    own_item_codes: list[str] = Field(default_factory=list)
    own_agency_names: list[str] = Field(default_factory=list)
    as_of: date | None = None


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.post("/analyze")
def analyze_cdas_booking(
    payload: CdasBookingAnalyseRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_member(context)
    as_of = payload.as_of or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    try:
        return analyse_cdas_booking(
            payload.raw_text,
            as_of=as_of,
            booking_lead_months=payload.booking_lead_months,
            own_item_codes=payload.own_item_codes,
            own_agency_names=payload.own_agency_names,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
