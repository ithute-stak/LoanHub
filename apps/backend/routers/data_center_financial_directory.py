"""Read-only financial status directories. Never a settlement, ledger or full snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.client_loan_company import ClientCompanyLoan
from database.models.payment import PaymentTransaction
from database.session import get_db
from services.data_center_branch_projection import verified_branch_grant
from services.data_center_financial_projection import (
    require_payment_directory_management,
    safe_loan_row,
    safe_payment_row,
)

router = APIRouter(prefix="/realtime/data-center", tags=["Data Center"])


@router.get("/loans")
def loan_directory(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        grant = verified_branch_grant(context)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Loan directory access denied") from None
    query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == context.company_id)
    if not grant.company_wide:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    records = query.order_by(ClientCompanyLoan.id).offset(offset).limit(limit + 1).all()
    try:
        if verified_branch_grant(context) != grant:
            raise PermissionError("Scope changed")
        safe = [safe_loan_row(row, grant) for row in records[:limit]]
    except PermissionError:
        raise HTTPException(status_code=403, detail="Loan directory access denied") from None
    return {
        "contract": "loanhub.directory-page.v1", "resource": "loans",
        "company_id": grant.company_id,
        "branch_id": None if grant.company_wide else grant.branch_id,
        "records": safe, "offset": offset, "limit": limit,
        "has_more": len(records) > limit, "complete_data_center_snapshot": False,
    }


@router.get("/payments")
def payment_directory(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        grant = verified_branch_grant(context)
        require_payment_directory_management(grant)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Payment directory access denied") from None
    query = db.query(PaymentTransaction).filter(PaymentTransaction.company_id == context.company_id)
    records = query.order_by(PaymentTransaction.id).offset(offset).limit(limit + 1).all()
    try:
        if verified_branch_grant(context) != grant:
            raise PermissionError("Scope changed")
        safe = [safe_payment_row(row, grant) for row in records[:limit]]
    except PermissionError:
        raise HTTPException(status_code=403, detail="Payment directory access denied") from None
    return {
        "contract": "loanhub.directory-page.v1", "resource": "payments",
        "company_id": grant.company_id, "branch_id": None,
        "records": safe, "offset": offset, "limit": limit,
        "has_more": len(records) > limit, "complete_data_center_snapshot": False,
    }
