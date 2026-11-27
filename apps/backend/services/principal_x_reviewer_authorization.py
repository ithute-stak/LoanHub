"""Internal maker/checker eligibility gate for Principal x ledger reviews.

Eligibility is not proof that either actor authenticated or approved evidence.
A future review workflow must bind both decisions to authenticated actors.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, UserRole
from database.models.user import User

MAKER_ROLES = frozenset({
    UserRole.COMPANY_OWNER, UserRole.FINANCE_OFFICER, UserRole.TREASURY_OFFICER,
})
CHECKER_ROLES = frozenset({
    UserRole.COMPANY_OWNER, UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER,
})


def require_independent_ledger_reviewers(
    db: Session, *, company_id: UUID, maker_user_id: UUID, checker_user_id: UUID,
) -> None:
    """Require active company-wide memberships, independently eligible actors.

    Call in the same PostgreSQL transaction as evidence persistence. Row locks
    prevent concurrent changes to the selected company, users and memberships.
    No global/platform role grants implicit tenant authority.
    """
    if not all(isinstance(value, UUID) for value in (
        company_id, maker_user_id, checker_user_id,
    )):
        raise ValueError("Verified reviewer scope required")
    if maker_user_id == checker_user_id:
        raise ValueError("Independent maker and checker required")
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("Reviewer authorization requires PostgreSQL")
    with db.no_autoflush:
        company = db.execute(
            select(LoanCompany).where(LoanCompany.id == company_id)
            .with_for_update(read=True).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if company is None or not company.is_active or company.status != CompanyStatus.APPROVED:
            raise ValueError("Active approved company required")
        actors = db.execute(
            select(User).where(User.id.in_([maker_user_id, checker_user_id]))
            .order_by(User.id).with_for_update(read=True)
            .execution_options(populate_existing=True)
        ).scalars().all()
        if len(actors) != 2 or any(not user.is_active for user in actors):
            raise ValueError("Active independent reviewers required")
        memberships = db.execute(
            select(CompanyStaff).where(
                CompanyStaff.company_id == company_id,
                CompanyStaff.user_id.in_([maker_user_id, checker_user_id]),
            ).order_by(CompanyStaff.id).with_for_update(read=True)
            .execution_options(populate_existing=True)
        ).scalars().all()
        eligible = {
            actor: {row.role for row in memberships
                    if row.user_id == actor and row.is_active and row.branch_id is None}
            for actor in (maker_user_id, checker_user_id)
        }
        if not eligible[maker_user_id].intersection(MAKER_ROLES):
            raise ValueError("Maker lacks company-wide financial review authority")
        if not eligible[checker_user_id].intersection(CHECKER_ROLES):
            raise ValueError("Checker lacks independent company-wide review authority")
