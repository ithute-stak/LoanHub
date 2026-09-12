from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, get_user_context
from database.models.company import LoanCompany
from database.models.file_sharing import CompanySocialShareSettings
from database.models.user import User
from database.schemas.file_sharing import (
    CompanySocialShareSettingsRead,
    CompanySocialShareSettingsUpdate,
)
from database.session import get_db

router = APIRouter(prefix="/companies", tags=["Company Social Sharing"])


def company_or_404(db: Session, company_id: UUID) -> LoanCompany:
    company = db.get(LoanCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def assert_company_scope(context: TenantContext, company_id: UUID, *, manage: bool = False) -> None:
    if context.is_platform_admin:
        return
    if context.company_id != company_id or not context.staff:
        raise HTTPException(status_code=403, detail="Cross-company access is not allowed")
    if manage and context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Company owner or administrator permission is required")


def settings_for(db: Session, company_id: UUID) -> CompanySocialShareSettings:
    row = (
        db.query(CompanySocialShareSettings)
        .filter(CompanySocialShareSettings.company_id == company_id)
        .first()
    )
    if row:
        return row
    row = CompanySocialShareSettings(
        company_id=company_id,
        external_sharing_enabled=False,
        default_expiry_hours=24,
        default_message="A secure LoanHub document has been shared with you.",
        enabled_channels=["native", "copy", "whatsapp", "email"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{company_id}/social-sharing", response_model=CompanySocialShareSettingsRead)
def get_social_sharing_settings(
    company_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_or_404(db, company_id)
    assert_company_scope(context, company_id)
    return settings_for(db, company_id)


@router.put("/{company_id}/social-sharing", response_model=CompanySocialShareSettingsRead)
def update_social_sharing_settings(
    company_id: UUID,
    payload: CompanySocialShareSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_or_404(db, company_id)
    assert_company_scope(context, company_id, manage=True)
    row = settings_for(db, company_id)
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    row.configured_by_user_id = context.user.id
    db.commit()
    db.refresh(row)
    return row
