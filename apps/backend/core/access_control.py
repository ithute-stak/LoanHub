from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from core.security import get_current_user
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, UserRole
from database.models.user import User
from database.session import get_db


PLATFORM_ROLES: set[UserRole] = {
    UserRole.SUPERADMIN,
    UserRole.PLATFORM_ADMIN,
    UserRole.PLATFORM_FINANCE,
    UserRole.PLATFORM_SUPPORT,
    UserRole.PLATFORM_AUDITOR,
    UserRole.PLATFORM_OPERATIONS,
    UserRole.PLATFORM_COMPLIANCE,
}
PLATFORM_ADMIN_ROLES: set[UserRole] = {
    UserRole.SUPERADMIN,
    UserRole.PLATFORM_ADMIN,
}
PLATFORM_FINANCE_ROLES: set[UserRole] = {
    UserRole.SUPERADMIN,
    UserRole.PLATFORM_ADMIN,
    UserRole.PLATFORM_FINANCE,
    UserRole.PLATFORM_AUDITOR,
    UserRole.PLATFORM_COMPLIANCE,
}
PLATFORM_SUPPORT_ROLES: set[UserRole] = {
    UserRole.SUPERADMIN,
    UserRole.PLATFORM_ADMIN,
    UserRole.PLATFORM_SUPPORT,
    UserRole.PLATFORM_OPERATIONS,
}

COMPANY_MANAGEMENT_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
}

BRANCH_MANAGEMENT_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.OPERATIONS_OFFICER,
}

LENDING_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
    UserRole.CREDIT_ANALYST,
}

FINANCE_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.FINANCE_OFFICER,
    UserRole.TREASURY_OFFICER,
}

COLLECTIONS_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.COLLECTIONS_OFFICER,
}

CASHIER_ROLES: set[UserRole] = FINANCE_ROLES | COLLECTIONS_ROLES

READ_ONLY_COMPANY_ROLES: set[UserRole] = {
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.CUSTOMER_SUPPORT,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.IT_SUPPORT,
    UserRole.AML_CFT_OFFICER,
    UserRole.DATA_PROTECTION_OFFICER,
    UserRole.REGULATORY_REPORTING_OFFICER,
    UserRole.INFORMATION_SECURITY_OFFICER,
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
    UserRole.CREDIT_ANALYST,
    UserRole.AML_CFT_OFFICER,
    UserRole.TREASURY_OFFICER,
    UserRole.DATA_PROTECTION_OFFICER,
    UserRole.REGULATORY_REPORTING_OFFICER,
    UserRole.OPERATIONS_OFFICER,
    UserRole.INFORMATION_SECURITY_OFFICER,
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
        if self.staff:
            return self.staff.role
        return self.user.role


def is_platform_role(role: UserRole | None) -> bool:
    return bool(role and role in PLATFORM_ROLES)


def is_platform_admin_role(role: UserRole | None) -> bool:
    return bool(role and role in PLATFORM_ADMIN_ROLES)


def get_current_active_user(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    if current_user.must_change_password and request.url.path not in {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "Change the temporary password before continuing.",
            },
        )
    return current_user


def require_platform_roles(
    current_user: User,
    allowed_roles: Iterable[UserRole],
) -> User:
    if current_user.role not in set(allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This platform role does not have permission for the operation",
        )
    return current_user


def require_platform_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    return require_platform_roles(current_user, PLATFORM_ADMIN_ROLES)


def require_platform_owner(
    current_user: User = Depends(get_current_active_user),
) -> User:
    return require_platform_roles(current_user, {UserRole.SUPERADMIN})


def require_platform_finance(
    current_user: User = Depends(get_current_active_user),
) -> User:
    return require_platform_roles(current_user, PLATFORM_FINANCE_ROLES)


def require_platform_support(
    current_user: User = Depends(get_current_active_user),
) -> User:
    return require_platform_roles(current_user, PLATFORM_SUPPORT_ROLES)


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


def _parse_active_role(value: str | None) -> UserRole | None:
    if not value:
        return None
    try:
        role = UserRole(value.strip().lower())
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Active-Role is not a recognised role",
        ) from error
    if role not in COMPANY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Active-Role must be a company role",
        )
    return role


def resolve_tenant_context(
    db: Session,
    current_user: User,
    x_company_id: str | None = None,
    x_active_role: str | None = None,
) -> TenantContext:
    if is_platform_admin_role(current_user.role):
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=True,
        )
    if is_platform_role(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This platform staff account is not a tenant-company account",
        )

    requested_company_id = _parse_company_header(x_company_id)
    requested_role = _parse_active_role(x_active_role)

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

    memberships = query.order_by(
        CompanyStaff.is_primary.desc(),
        CompanyStaff.created_at.asc(),
    ).all()

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active loan-company membership was found for this account",
        )

    company_ids = {membership.company_id for membership in memberships}
    if not requested_company_id and len(company_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account belongs to multiple companies. "
                "Send the selected company in the X-Company-ID header."
            ),
        )

    selected_company_id = requested_company_id or memberships[0].company_id
    company_memberships = [
        membership
        for membership in memberships
        if membership.company_id == selected_company_id
    ]

    if requested_role:
        staff = next(
            (membership for membership in company_memberships if membership.role == requested_role),
            None,
        )
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The selected role is not assigned to this account for the active company",
            )
    else:
        staff = next(
            (membership for membership in company_memberships if membership.is_primary),
            company_memberships[0],
        )

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
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    return resolve_tenant_context(db, current_user, x_company_id, x_active_role)


def get_optional_tenant_context(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """Return tenant context when the caller is a company user and a neutral
    platform context for platform staff.

    This is intended for shared finance/support endpoints that may be called
    either by tenant staff or by a platform role. It deliberately does not
    grant tenant scope to platform staff; route-level permissions still decide
    which records a platform role may access.
    """
    if is_platform_role(current_user.role):
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=is_platform_admin_role(current_user.role),
        )
    if current_user.role == UserRole.BORROWER:
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=False,
        )
    return resolve_tenant_context(db, current_user, x_company_id, x_active_role)


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

    if context.staff.role in COMPANY_MANAGEMENT_ROLES:
        return

    if context.branch_id is not None and context.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This record belongs to another company branch",
        )


def get_user_context(
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
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
    if is_platform_role(current_user.role):
        return TenantContext(
            user=current_user,
            staff=None,
            company=None,
            company_id=None,
            branch_id=None,
            is_platform_admin=is_platform_admin_role(current_user.role),
        )
    return resolve_tenant_context(db, current_user, x_company_id, x_active_role)
