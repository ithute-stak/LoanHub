"""Non-routed issuer membership recheck for official LoanHub document issuance.

The request TenantContext is not accepted as proof of a durable staff grant:
reload current user, active company, and active company-management membership
from persisted records immediately before an issuance attempt.

This is an application authorization gate, NOT a database SECURITY DEFINER
authentication primitive. No public endpoints or privileged SQL are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus
from database.models.user import User


@dataclass(frozen=True)
class AuthorizedIssuer:
    user_id: UUID
    company_id: UUID
    staff_id: UUID
    role: str


def require_current_document_issuer(
    *, db: Session, context: TenantContext,
) -> AuthorizedIssuer:
    """Reload live staff/company status, bypassing previously cached ORM objects.

    Acquire delegated PostgreSQL SHARE NOWAIT locks on all three records,
    then re-read them under tenant RLS. The issuer has SELECT-only grants;
    the protected lock function must be provisioned and executable, or fail closed.
    """
    if (context.is_platform_admin or context.user is None
            or context.staff is None or context.company is None
            or not isinstance(context.user.id, UUID)
            or not isinstance(context.staff.id, UUID)
            or not isinstance(context.company_id, UUID)
            or context.company.id != context.company_id
            or context.staff.company_id != context.company_id
            or context.staff.user_id != context.user.id
            or context.staff.role not in COMPANY_MANAGEMENT_ROLES):
        raise PermissionError("Current authenticated company issuer required")

    # A database-owner SECURITY DEFINER function checks the protected
    # session_user/company mapping and locks authorization rows without
    # granting this SQL login UPDATE. Never fall back to an unlocked read.
    locked = db.execute(text(
        "SELECT public.lock_document_issuer_authorization(:user_id, :company_id, :staff_id)"
    ), {
        "user_id": context.user.id,
        "company_id": context.company_id,
        "staff_id": context.staff.id,
    }).scalar_one_or_none()
    if locked is not True:
        raise PermissionError("Delegated issuer authorization lock was not acquired")

    user = db.query(User).filter(
        User.id == context.user.id,
        User.is_active.is_(True),
        User.must_change_password.is_(False),
    ).populate_existing().one_or_none()
    if (user is None or user.id != context.user.id
            or user.is_active is not True
            or user.must_change_password is not False):
        raise PermissionError("Issuer account is inactive or requires reauthentication")

    company = db.query(LoanCompany).filter(
        LoanCompany.id == context.company_id,
        LoanCompany.is_active.is_(True),
        LoanCompany.status == CompanyStatus.APPROVED,
    ).populate_existing().one_or_none()
    if (company is None or company.id != context.company_id
            or company.is_active is not True
            or company.status != CompanyStatus.APPROVED):
        raise PermissionError("Issuer company is not currently approved")

    membership = db.query(CompanyStaff).filter(
        CompanyStaff.id == context.staff.id,
        CompanyStaff.user_id == context.user.id,
        CompanyStaff.company_id == context.company_id,
        CompanyStaff.is_active.is_(True),
        CompanyStaff.role.in_(COMPANY_MANAGEMENT_ROLES),
    ).populate_existing().one_or_none()
    if (membership is None or membership.id != context.staff.id
            or membership.user_id != context.user.id
            or membership.company_id != context.company_id
            or membership.is_active is not True
            or membership.role not in COMPANY_MANAGEMENT_ROLES
            or membership.role != context.staff.role):
        raise PermissionError("Company issuer membership was revoked or changed")
    return AuthorizedIssuer(
        user_id=user.id, company_id=company.id, staff_id=membership.id,
        role=membership.role.value,
    )
