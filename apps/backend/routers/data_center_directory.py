"""Read-only, authenticated branch directory projection.

This endpoint is a narrowly-scoped integration step, NOT a complete data-center
snapshot. The frontend must not consider six-resource sync current from it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.branch import CompanyBranch
from database.models.loan_product import LoanProduct
from services.data_center_loan_product_projection import safe_loan_product_row
from database.session import get_db
from services.data_center_branch_projection import safe_branch_row, verified_branch_grant

router = APIRouter(prefix="/realtime/data-center", tags=["Data Center"])


@router.get("/branches")
def branch_directory(
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
        raise HTTPException(status_code=403, detail="Branch directory access denied") from None
    query = db.query(CompanyBranch).filter(CompanyBranch.company_id == context.company_id)
    if not grant.company_wide:
        query = query.filter(CompanyBranch.id == context.branch_id)
    records = query.order_by(CompanyBranch.id).offset(offset).limit(limit + 1).all()
    try:
        if verified_branch_grant(context) != grant:
            raise PermissionError("Scope changed")
        safe = [safe_branch_row(row, grant) for row in records[:limit]]
    except PermissionError:
        raise HTTPException(status_code=403, detail="Branch directory access denied") from None
    return {
        "contract": "loanhub.directory-page.v1",
        "resource": "branches",
        "company_id": grant.company_id,
        "branch_id": None if grant.company_wide else grant.branch_id,
        "records": safe,
        "offset": offset,
        "limit": limit,
        "has_more": len(records) > limit,
        "complete_data_center_snapshot": False,
    }


@router.get("/loan-products")
def loan_product_directory(
    response: Response,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read-only, company-scoped product labels, never financial policy data.

    This is a directory page, not a full Data Center snapshot or replay.
    """
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        grant = verified_branch_grant(context)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Loan product directory access denied") from None
    query = db.query(LoanProduct).filter(LoanProduct.company_id == context.company_id)
    records = query.order_by(LoanProduct.id).offset(offset).limit(limit + 1).all()
    try:
        if verified_branch_grant(context) != grant:
            raise PermissionError("Scope changed")
        safe = [safe_loan_product_row(row, grant) for row in records[:limit]]
    except PermissionError:
        raise HTTPException(status_code=403, detail="Loan product directory access denied") from None
    return {
        "contract": "loanhub.directory-page.v1",
        "resource": "loanProducts",
        "company_id": grant.company_id,
        "branch_id": None if grant.company_wide else grant.branch_id,
        "records": safe,
        "offset": offset,
        "limit": limit,
        "has_more": len(records) > limit,
        "complete_data_center_snapshot": False,
    }
