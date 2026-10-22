from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date
from database.models.repayment import RepaymentInstallment

from core.access_control import COMPANY_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.client_loan_company import ClientCompanyLoan
from database.session import get_db
from routers.folio_book import _base_query, _integrity, _row
from services.folio_book_report_service import build_folio_book_pdf
from services.overdue_portfolio_report_service import build_overdue_portfolio_pdf


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


class OverduePortfolioExportRequest(BaseModel):
    loan_ids: list[UUID] = Field(min_length=1, max_length=2000)


@router.post("/overdue-export.pdf")
def export_filtered_overdue_pdf(
    payload: OverduePortfolioExportRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    ids = set(payload.loan_ids)
    # Rebuild from authoritative tenant-scoped database state, not browser-supplied balances.
    loans = _base_query(db, context).filter(ClientCompanyLoan.id.in_(ids)).all()
    if len(loans) != len(ids):
        raise HTTPException(status_code=400, detail="Selection contains unavailable loans.")
    if any(
        not loan.is_overdue or float(loan.balance or 0) <= 0
        or str(getattr(loan.status, "value", loan.status)) not in {"active", "defaulted"}
        for loan in loans
    ):
        raise HTTPException(status_code=400, detail="Selection contains loans that are no longer overdue. Refresh the portfolio.")
    installments = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.loan_id.in_(ids),
        RepaymentInstallment.is_superseded.is_(False),
        RepaymentInstallment.due_date < date.today(),
        RepaymentInstallment.total_due > RepaymentInstallment.paid_amount,
    ).order_by(RepaymentInstallment.due_date.asc()).all()
    earliest_due = {}
    for installment in installments:
        earliest_due.setdefault(installment.loan_id, installment.due_date)
    rows = []
    for loan in sorted(loans, key=lambda item: (str(item.folio_number or ""), str(item.loan_reference))):
        row = _row(loan)
        row["due_date"] = earliest_due[loan.id].isoformat() if loan.id in earliest_due else "Not available"
        row["installment_amount"] = float(loan.installment_amount or 0)
        rows.append(row)
    pdf = build_overdue_portfolio_pdf(db=db, context=context, rows=rows)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=loanhub-overdue-debts.pdf",
                 "Cache-Control": "no-store"},
    )
