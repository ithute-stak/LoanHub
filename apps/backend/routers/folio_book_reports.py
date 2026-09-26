from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.client_loan_company import ClientCompanyLoan
from database.session import get_db
from routers.folio_book import _base_query, _integrity, _row
from services.folio_book_report_service import build_folio_book_pdf


router = APIRouter(prefix="/folio-book", tags=["Loan Folio Book"])


@router.get("/export.pdf")
def export_folio_book_pdf(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    loans = _base_query(db, context).order_by(
        ClientCompanyLoan.folio_group_code.asc(),
        ClientCompanyLoan.folio_sequence.asc(),
    ).all()
    rows = [_row(item) for item in loans]
    content = build_folio_book_pdf(
        db=db,
        context=context,
        rows=rows,
        integrity=_integrity(loans),
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=loanhub-folio-book.pdf"},
    )
