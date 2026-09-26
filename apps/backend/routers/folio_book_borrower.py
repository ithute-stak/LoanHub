from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.client_loan_company import ClientCompanyLoan
from database.session import get_db
from routers.folio_book import _base_query, _row


router = APIRouter(prefix="/folio-book", tags=["Loan Folio Book"])


@router.get("/borrowers/{borrower_id}")
def borrower_folio_history(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    loans = (
        _base_query(db, context)
        .filter(ClientCompanyLoan.borrower_id == borrower_id)
        .order_by(ClientCompanyLoan.created_at.asc(), ClientCompanyLoan.folio_sequence.asc())
        .all()
    )
    if not loans:
        raise HTTPException(status_code=404, detail="No loans were found for this borrower in the active company scope")
    return {
        "borrower_id": str(borrower_id),
        "borrower_name": _row(loans[0])["borrower_name"],
        "loan_count": len(loans),
        "folios": [_row(item) for item in loans],
    }
