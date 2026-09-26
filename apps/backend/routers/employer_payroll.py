from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.employer_payroll import EmployerPayrollAccount, EmployerPayrollEmployee
from database.models.user import User
from database.session import get_db
from services.employer_payroll_report_service import build_payroll_reconciliation_pdf
from services.employer_payroll_service import (
    account_payload,
    build_overview,
    cycle_payload,
    deduction_payload,
    employee_payload,
    generate_cycle,
    get_account,
    get_cycle,
    import_cycle_csv,
    list_cycles,
    list_exceptions,
    money,
    reconcile_cycle,
    set_employee_state,
    upsert_account,
)


router = APIRouter(prefix="/employer-payroll", tags=["Employer & Payroll Management"])
PAYROLL_WRITE_ROLES = LENDING_ROLES | FINANCE_ROLES | COLLECTIONS_ROLES
COLLECTION_CHANNELS = {"employer_payroll", "cdas", "mixed", "manual"}


class PayrollAccountUpsert(BaseModel):
    employer_group_id: UUID
    payroll_reference: str | None = Field(default=None, max_length=100)
    payroll_day: int | None = Field(default=None, ge=1, le=31)
    collection_channel: str = Field(default="employer_payroll", max_length=40)
    reconciliation_tolerance: Decimal = Field(default=Decimal("0.00"), ge=0)
    payroll_contact_name: str | None = Field(default=None, max_length=200)
    payroll_contact_email: str | None = Field(default=None, max_length=255)
    payroll_contact_phone: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool = True


class PayrollCycleGenerate(BaseModel):
    period_key: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    scheduled_pay_date: date | None = None


class PayrollEmployeeUpdate(BaseModel):
    employee_number: str | None = Field(default=None, max_length=100)
    employment_state: str = Field(default="active", max_length=30)
    effective_date: date | None = None
    termination_date: date | None = None
    termination_reason: str | None = Field(default=None, max_length=4000)


def _write_access(context: TenantContext) -> None:
    require_tenant_roles(context, PAYROLL_WRITE_ROLES)


def _borrower_for_company(db: Session, context: TenantContext, borrower_id: UUID) -> Borrower:
    loan_query = db.query(ClientCompanyLoan.id).filter(
        ClientCompanyLoan.company_id == context.company_id,
        ClientCompanyLoan.borrower_id == borrower_id,
    )
    if context.branch_id:
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    if not loan_query.first():
        raise HTTPException(status_code=404, detail="Borrower was not found in the active company/branch loan portfolio")
    borrower = (
        db.query(Borrower)
        .options(joinedload(Borrower.user).joinedload(User.person), joinedload(Borrower.employer_group))
        .filter(Borrower.id == borrower_id)
        .first()
    )
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower was not found")
    return borrower


@router.get("/overview")
def employer_payroll_overview(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    return build_overview(db, context)


@router.get("/accounts")
def employer_payroll_accounts(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    rows = (
        db.query(EmployerPayrollAccount)
        .options(joinedload(EmployerPayrollAccount.employer_group))
        .filter(EmployerPayrollAccount.company_id == context.company_id)
        .order_by(EmployerPayrollAccount.created_at.asc())
        .all()
    )
    return [account_payload(row) for row in rows]


@router.put("/accounts")
def configure_employer_payroll_account(
    payload: PayrollAccountUpsert,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _write_access(context)
    channel = payload.collection_channel.strip().lower()
    if channel not in COLLECTION_CHANNELS:
        raise HTTPException(status_code=422, detail=f"Collection channel must be one of: {', '.join(sorted(COLLECTION_CHANNELS))}")
    account = upsert_account(
        db,
        context,
        employer_group_id=payload.employer_group_id,
        payroll_reference=payload.payroll_reference,
        payroll_day=payload.payroll_day,
        collection_channel=channel,
        reconciliation_tolerance=payload.reconciliation_tolerance,
        payroll_contact_name=payload.payroll_contact_name,
        payroll_contact_email=payload.payroll_contact_email,
        payroll_contact_phone=payload.payroll_contact_phone,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    return account_payload(account)


@router.get("/accounts/{account_id}")
def employer_payroll_account_detail(
    account_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    account = get_account(db, context, account_id)
    result = account_payload(account)
    result["employees"] = [employee_payload(row) for row in account.employees]
    result["cycles"] = [cycle_payload(row) for row in list_cycles(db, context, account_id=account.id, limit=24)]
    return result


@router.get("/employees")
def employer_payroll_employees(
    account_id: UUID | None = None,
    employment_state: str | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    query = db.query(EmployerPayrollEmployee).options(
        joinedload(EmployerPayrollEmployee.borrower).joinedload(Borrower.user).joinedload(User.person),
    ).filter(EmployerPayrollEmployee.company_id == context.company_id)
    if account_id:
        account = get_account(db, context, account_id)
        query = query.filter(EmployerPayrollEmployee.employer_account_id == account.id)
    if employment_state:
        query = query.filter(EmployerPayrollEmployee.employment_state == employment_state.strip().lower())
    rows = query.order_by(EmployerPayrollEmployee.updated_at.desc()).limit(limit).all()
    if context.branch_id:
        allowed_borrowers = {
            row[0] for row in db.query(ClientCompanyLoan.borrower_id).filter(
                ClientCompanyLoan.company_id == context.company_id,
                ClientCompanyLoan.branch_id == context.branch_id,
            ).distinct().all()
        }
        rows = [row for row in rows if row.borrower_id in allowed_borrowers]
    return [employee_payload(row) for row in rows]


@router.put("/accounts/{account_id}/employees/{borrower_id}")
def update_employer_payroll_employee(
    account_id: UUID,
    borrower_id: UUID,
    payload: PayrollEmployeeUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _write_access(context)
    account = get_account(db, context, account_id)
    borrower = _borrower_for_company(db, context, borrower_id)
    employee = set_employee_state(
        db,
        context,
        account,
        borrower,
        employee_number=payload.employee_number,
        employment_state=payload.employment_state,
        effective_date=payload.effective_date,
        termination_date=payload.termination_date,
        termination_reason=payload.termination_reason,
    )
    return employee_payload(employee)


@router.get("/cycles")
def employer_payroll_cycles(
    account_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    if account_id:
        get_account(db, context, account_id)
    return [cycle_payload(row) for row in list_cycles(db, context, account_id=account_id, limit=limit)]


@router.post("/accounts/{account_id}/cycles")
def create_employer_payroll_cycle(
    account_id: UUID,
    payload: PayrollCycleGenerate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _write_access(context)
    account = get_account(db, context, account_id)
    cycle = generate_cycle(
        db,
        context,
        account,
        period_key=payload.period_key,
        scheduled_pay_date=payload.scheduled_pay_date,
    )
    return cycle_payload(cycle, include_lines=True)


@router.get("/cycles/{cycle_id}")
def employer_payroll_cycle_detail(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    return cycle_payload(get_cycle(db, context, cycle_id), include_lines=True)


@router.post("/cycles/{cycle_id}/import.csv")
async def import_employer_payroll_csv(
    cycle_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _write_access(context)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV payroll file")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payroll CSV is limited to 5 MB")
    return import_cycle_csv(db, context, get_cycle(db, context, cycle_id), content)


@router.post("/cycles/{cycle_id}/reconcile")
def reconcile_employer_payroll_cycle(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _write_access(context)
    cycle = reconcile_cycle(db, context, get_cycle(db, context, cycle_id))
    return cycle_payload(cycle, include_lines=True)


@router.get("/exceptions")
def employer_payroll_exceptions(
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    return [deduction_payload(row) for row in list_exceptions(db, context, limit=limit)]


@router.get("/cycles/{cycle_id}/export.csv")
def export_employer_payroll_cycle_csv(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    cycle = get_cycle(db, context, cycle_id)
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=[
        "folio_number", "loan_reference", "borrower_name", "employee_number",
        "expected_amount", "actual_amount", "variance_amount", "status",
        "rejection_code", "rejection_reason", "employer_reference",
    ])
    writer.writeheader()
    for line in cycle.deductions:
        payload = deduction_payload(line)
        writer.writerow({key: payload.get(key) for key in writer.fieldnames})
    group_code = cycle.account.employer_group.code if cycle.account and cycle.account.employer_group else "payroll"
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=payroll-{group_code}-{cycle.period_key}.csv"},
    )


@router.get("/cycles/{cycle_id}/export.pdf")
def export_employer_payroll_cycle_pdf(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_ROLES)
    cycle = get_cycle(db, context, cycle_id)
    content = build_payroll_reconciliation_pdf(db, cycle)
    group_code = cycle.account.employer_group.code if cycle.account and cycle.account.employer_group else "payroll"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=payroll-{group_code}-{cycle.period_key}.pdf"},
    )
