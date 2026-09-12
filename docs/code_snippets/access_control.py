from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from core.security import get_current_user
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, UserRole
from database.models.user import User
from database.session import get_db


COMPANY_MANAGEMENT_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
}

BRANCH_MANAGEMENT_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
}

LENDING_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
}

FINANCE_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.FINANCE_OFFICER,
}

COLLECTIONS_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.COLLECTIONS_OFFICER,
}

READ_ONLY_COMPANY_ROLES: set[UserRole] = {
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.CUSTOMER_SUPPORT,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.IT_SUPPORT,
}


HR_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.HR_MANAGER,
}

PERFORMANCE_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.AUDITOR,
}

TRANSPARENCY_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.IT_SUPPORT,
}

COMPANY_ROLES: set[UserRole] = (
    COMPANY_MANAGEMENT_ROLES
    | BRANCH_MANAGEMENT_ROLES
    | LENDING_ROLES
    | FINANCE_ROLES
    | COLLECTIONS_ROLES
    | READ_ONLY_COMPANY_ROLES
)


@dataclass(frozen=True, slots=True)
class TenantContext:
    user: User
    staff: CompanyStaff | None
    company: LoanCompany | None
    company_id: UUID | None
    branch_id: UUID | None
    is_platform_admin: bool

    @property
    def role(self) -> UserRole:
        if self.is_platform_admin:
            return UserRole.SUPERADMIN
        if self.staff:
            return self.staff.role
        return self.user.role


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return current_user


def require_platform_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator permission is required",
        )
    return current_user


def _parse_company_header(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Company-ID must be a valid UUID",
        ) from error


def resolve_tenant_context(
    db: Session,
    current_user: User,
    x_company_id: str | None = None,
) -> TenantContext:
    if current_user.role == UserRole.SUPERADMIN:
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=True,
        )

    requested_company_id = _parse_company_header(x_company_id)

    query = (
        db.query(CompanyStaff)
        .options(joinedload(CompanyStaff.company))
        .filter(
            CompanyStaff.user_id == current_user.id,
            CompanyStaff.is_active.is_(True),
        )
    )

    if requested_company_id:
        query = query.filter(CompanyStaff.company_id == requested_company_id)

    memberships = query.order_by(CompanyStaff.created_at.asc()).all()

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active loan-company membership was found for this account",
        )

    if not requested_company_id and len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account belongs to multiple companies. "
                "Send the selected company in the X-Company-ID header."
            ),
        )

    staff = memberships[0]
    company = staff.company

    if not company:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The staff membership is not linked to a company",
        )

    if company.status != CompanyStatus.APPROVED or not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The selected company is not approved and active",
        )

    return TenantContext(
        user=current_user,
        staff=staff,
        company=company,
        company_id=staff.company_id,
        branch_id=staff.branch_id,
        is_platform_admin=False,
    )


def get_tenant_context(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    return resolve_tenant_context(db, current_user, x_company_id)


def require_tenant_roles(
    context: TenantContext,
    allowed_roles: Iterable[UserRole],
) -> None:
    if context.is_platform_admin:
        return

    allowed = set(allowed_roles)
    if not context.staff or context.staff.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this company operation",
        )


def assert_company_scope(
    context: TenantContext,
    company_id: UUID,
) -> None:
    if context.is_platform_admin:
        return
    if context.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-company access is not allowed",
        )


def assert_branch_scope(
    context: TenantContext,
    branch_id: UUID | None,
) -> None:
    if context.is_platform_admin or not context.staff:
        return

    # Company owners and company administrators have company-wide visibility.
    if context.staff.role in COMPANY_MANAGEMENT_ROLES:
        return

    # Other staff accounts become branch-scoped whenever their membership has
    # a branch assignment. This prevents a user from guessing an ID belonging
    # to another branch even when both branches belong to the same company.
    if context.branch_id is not None and context.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This record belongs to another company branch",
        )



def get_user_context(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Resolve a secure context for platform admins, borrowers and company users."""
    if current_user.role == UserRole.BORROWER:
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=False,
        )
    return resolve_tenant_context(db, current_user, x_company_id)
