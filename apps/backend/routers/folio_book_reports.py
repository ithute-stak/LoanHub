from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import date
from decimal import Decimal
from collections import defaultdict
from database.models.repayment import RepaymentInstallment
from database.models.origination import BorrowerEmploymentProfile
from services.folio_due_report_service import build_folio_due_pdf
from services.folio_next_installment_report_service import build_folio_next_installment_pdf
from services.legacy_loan_lock_policy import apply_legacy_loan_visibility

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
        user = loan.borrower.user if loan.borrower else None
        row["contact_phone"] = user.phone if user else None
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


@router.get("/due-installments.pdf")
def export_group_due_installments_pdf(
    group_code: str | None = None,
    through_date: date | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Tenant-scoped unpaid installments due through the selected date.

    Group is a server-side folio filter. Never trust balances or borrower
    contact fields supplied by the browser.
    """
    require_tenant_roles(context, COMPANY_ROLES)
    cutoff = through_date or date.today()
    if cutoff > date.today():
        raise HTTPException(status_code=422, detail="Due report date cannot be in the future")
    loans_query = _base_query(db, context).filter(
        ClientCompanyLoan.status.in_(["active", "defaulted"]),
        ClientCompanyLoan.balance > 0,
    )
    if group_code:
        if len(group_code) > 40:
            raise HTTPException(status_code=422, detail="Invalid work group")
        loans_query = loans_query.filter(ClientCompanyLoan.folio_group_code == group_code)
    loans = loans_query.all()
    if not loans:
        rows = []
    else:
        loan_by_id = {loan.id: loan for loan in loans}
        installments = db.query(RepaymentInstallment).filter(
            RepaymentInstallment.loan_id.in_(list(loan_by_id)),
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.due_date <= cutoff,
            RepaymentInstallment.total_due > RepaymentInstallment.paid_amount,
        ).order_by(RepaymentInstallment.due_date).all()
        due_by_loan = defaultdict(lambda: Decimal("0"))
        earliest = {}
        for item in installments:
            due_by_loan[item.loan_id] += max(Decimal("0"), Decimal(item.total_due) - Decimal(item.paid_amount or 0))
            earliest.setdefault(item.loan_id, item.due_date)
        borrower_ids = {loan_by_id[loan_id].borrower_id for loan_id in due_by_loan}
        employment = db.query(BorrowerEmploymentProfile).filter(
            BorrowerEmploymentProfile.company_id == context.company_id,
            BorrowerEmploymentProfile.borrower_id.in_(borrower_ids),
        ).all() if borrower_ids else []
        occupation_by_borrower = {row.borrower_id: row.job_title for row in employment}
        rows = []
        for loan_id, due in due_by_loan.items():
            loan = loan_by_id[loan_id]
            row = _row(loan)
            user = loan.borrower.user if loan.borrower else None
            row["contact_phone"] = user.phone if user else None
            row["occupation"] = occupation_by_borrower.get(loan.borrower_id) or row.get("employer_name")
            row["due_date"] = earliest[loan_id].isoformat()
            row["due_amount"] = min(due, Decimal(loan.balance or 0))
            rows.append(row)
        rows.sort(key=lambda row: (str(row.get("folio_number") or ""), str(row.get("loan_reference") or "")))
    pdf = build_folio_due_pdf(db=db, context=context, rows=rows, group_code=group_code, through_date=cutoff)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=loanhub-folio-due-installments.pdf",
        "Cache-Control": "no-store",
    })


@router.get("/next-installments.pdf")
def export_next_installments_pdf(
    group_code: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=40),
    search: str | None = Query(default=None, max_length=200),
    branch_id: UUID | None = None,
    loan_from_date: date = Query(default=date(2026, 9, 1)),
    from_date: date | None = None,
    through_date: date | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """One earliest outstanding, non-superseded installment per active loan."""
    require_tenant_roles(context, COMPANY_ROLES)
    if from_date and through_date and from_date > through_date:
        raise HTTPException(status_code=422, detail="Start date must not exceed end date")
    query = _base_query(db, context).filter(
        ClientCompanyLoan.status.in_(["active", "defaulted"]),
        ClientCompanyLoan.balance > 0,
        ClientCompanyLoan.disbursed_at.is_not(None),
        ClientCompanyLoan.disbursed_at >= loan_from_date,
    )
    if group_code:
        query = query.filter(ClientCompanyLoan.folio_group_code == group_code)
    if status:
        if status not in {"active", "defaulted"}:
            query = query.filter(False)
        else:
            query = query.filter(ClientCompanyLoan.status == status)
    if branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == branch_id)
    loans = query.all()
    by_id = {loan.id: loan for loan in loans}
    installments = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.loan_id.in_(list(by_id)),
        RepaymentInstallment.is_superseded.is_(False),
        RepaymentInstallment.total_due > RepaymentInstallment.paid_amount,
    ).order_by(RepaymentInstallment.due_date.asc(), RepaymentInstallment.id.asc()).all() if by_id else []
    next_by_loan = {}
    for installment in installments:
        next_by_loan.setdefault(installment.loan_id, installment)
    rows = []
    term = (search or "").strip().casefold()
    for loan_id, installment in next_by_loan.items():
        loan = by_id[loan_id]
        due = installment.due_date
        if from_date and due < from_date:
            continue
        if through_date and due > through_date:
            continue
        row = _row(loan)
        if term and not any(term in str(row.get(key) or "").casefold() for key in (
            "folio_number", "loan_reference", "borrower_name", "borrower_identity",
            "employer_name", "employer_group_name", "branch_name", "status",
        )):
            continue
        user = loan.borrower.user if loan.borrower else None
        row["contact_phone"] = user.phone if user else None
        row["occupation"] = row.get("employer_group_name") or row.get("employer_name")
        row["due_date"] = due.isoformat()
        row["due_amount"] = min(
            max(Decimal("0"), Decimal(installment.total_due) - Decimal(installment.paid_amount or 0)),
            Decimal(loan.balance or 0),
        )
        rows.append(row)
    rows.sort(key=lambda row: (row["due_date"], row.get("folio_number") or "", row["loan_reference"]))
    pdf = build_folio_next_installment_pdf(
        db=db, context=context, rows=rows,
        group_code=group_code, from_date=from_date, through_date=through_date,
        loan_from_date=loan_from_date,
    )
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=loanhub-next-installments.pdf",
        "Cache-Control": "no-store",
    })
