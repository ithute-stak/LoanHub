from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COLLECTIONS_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import UserRole
from database.models.user import User
from database.session import get_db


router = APIRouter(prefix="/borrower-workspace", tags=["Borrower Workspace"])

BORROWER_WORKSPACE_ROLES = LENDING_ROLES | COLLECTIONS_ROLES | {
    UserRole.CUSTOMER_SUPPORT,
    UserRole.OPERATIONS_OFFICER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.RISK_MANAGER,
}


def _borrower_name(user: User) -> str:
    person = user.person
    if person is None:
        return user.email or user.phone or "Borrower"
    return " ".join(
        value
        for value in [person.first_name, person.middle_name, person.last_name]
        if value
    ) or user.email or user.phone or "Borrower"


@router.get("/{borrower_id}/context")
def borrower_workspace_context(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Resolve a borrower into the active company's borrower account.

    The borrower UUID is the canonical navigation key used by calls, collections,
    lending and servicing. Resolution is tenant- and branch-scoped so a borrower
    can safely appear in more than one lender without exposing another company's
    relationship data.
    """
    require_tenant_roles(context, BORROWER_WORKSPACE_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")

    account = (
        db.query(CompanyBorrowerAccount)
        .options(
            joinedload(CompanyBorrowerAccount.borrower)
            .joinedload(Borrower.user)
            .joinedload(User.person)
        )
        .filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.borrower_id == borrower_id,
        )
        .order_by(CompanyBorrowerAccount.created_at.desc())
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Borrower is not a client of the active company")

    assert_branch_scope(context, account.branch_id)
    borrower = account.borrower
    user = borrower.user
    person = user.person

    return {
        "account_id": str(account.id),
        "account_reference": account.account_reference,
        "account_status": account.status,
        "company_id": str(account.company_id),
        "branch_id": str(account.branch_id) if account.branch_id else None,
        "borrower_id": str(borrower.id),
        "name": _borrower_name(user),
        "phone": user.phone,
        "email": user.email,
        "national_id": person.national_id if person else None,
        "passport_number": person.passport_number if person else None,
        "physical_address": person.physical_address if person else None,
        "district": person.district if person else None,
        "town_or_village": person.town_or_village if person else None,
        "employment_status": getattr(borrower.employment_status, "value", borrower.employment_status),
        "employer_name": borrower.employer_name,
        "job_title": borrower.job_title,
        "monthly_income": float(borrower.monthly_income) if borrower.monthly_income is not None else None,
        "opened_at": account.created_at.isoformat() if account.created_at else None,
    }
