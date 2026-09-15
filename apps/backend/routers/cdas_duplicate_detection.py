from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasAnalysisRecord, CdasBookingOpportunity
from database.session import get_db
from services.cdas_client_profiles import build_client_profiles
from services.cdas_duplicate_detection import build_duplicate_detection

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Duplicate Detection"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.get("/duplicates")
def get_cdas_duplicate_detection(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return review-only duplicate candidates from tenant-scoped CDAS client profiles."""
    _require_company_member(context)
    analyses = db.query(CdasAnalysisRecord).filter(
        CdasAnalysisRecord.company_id == context.company_id
    ).order_by(
        CdasAnalysisRecord.created_at.desc(),
        CdasAnalysisRecord.id.desc(),
    ).all()
    opportunities = db.query(CdasBookingOpportunity).filter(
        CdasBookingOpportunity.company_id == context.company_id
    ).order_by(
        CdasBookingOpportunity.created_at.desc(),
        CdasBookingOpportunity.id.desc(),
    ).all()
    profiles = build_client_profiles(analyses, opportunities)
    return build_duplicate_detection(profiles)
