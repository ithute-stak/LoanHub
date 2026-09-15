from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.cdas_booking import CdasAnalysisRecord
from database.session import get_db
from services.cdas_change_detection import build_change_detection

router = APIRouter(prefix="/cdas-booking", tags=["CDAS Change Detection"])


def _require_company_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")


@router.get("/changes")
def get_cdas_changes(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Compare each exact client's newest archived CDAS analysis with its previous version."""
    _require_company_member(context)
    records = db.query(CdasAnalysisRecord).filter(
        CdasAnalysisRecord.company_id == context.company_id
    ).order_by(
        CdasAnalysisRecord.created_at.desc(),
        CdasAnalysisRecord.id.desc(),
    ).all()
    return build_change_detection(records)
