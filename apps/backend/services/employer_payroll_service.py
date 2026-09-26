from __future__ import annotations

import calendar
import csv
import hashlib
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import StringIO
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.employer_group import EmployerGroup
from database.models.employer_payroll import (
    EmployerPayrollAccount,
    EmployerPayrollCycle,
    EmployerPayrollDeduction,
    EmployerPayrollEmployee,
)
from database.models.enums import LoanStatus
from database.models.user import User


MONEY = Decimal("0.01")
ACTIVE_COLLECTION_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
EMPLOYMENT_STATES = {"active", "suspended", "terminated", "left_employer"}
DEDUCTION_EXCEPTION_STATUSES = {"shortage", "excess", "rejected", "missing", "terminated", "unmatched"}


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid money amount: {value!r}") from exc


def borrower_name(borrower: Borrower | None) -> str:
    user = borrower.user if borrower else None
    person = user.person if user else None
    if person:
        return person.full_name
    return user.email if user else "Borrower"


def _scoped_loans(db: Session, context: TenantContext):
    query = db.query(ClientCompanyLoan).options(
        joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.user).joinedload(User.person),
        joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.employer_group),
    ).filter(ClientCompanyLoan.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    return query


def _pay_date(period_key: str, payroll_day: int | None, explicit: date | None = None) -> date:
    try:
        year_text, month_text = period_key.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if month < 1 or month > 12:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Payroll period must use YYYY-MM format") from exc
    if explicit:
        if explicit.year != year or explicit.month != month:
            raise HTTPException(status_code=422, detail="Scheduled pay date must fall inside the payroll period")
        return explicit
    if not payroll_day:
        raise HTTPException(status_code=422, detail="Configure a payroll day or supply a scheduled pay date before generating a cycle")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(int(payroll_day), last_day))


def account_payload(account: EmployerPayrollAccount) -> dict[str, Any]:
    group = account.employer_group
    return {
        "id": str(account.id),
        "employer_group_id": str(account.employer_group_id),
        "group_code": group.code if group else None,
        "group_name": group.name if group else None,
        "branch_id": str(account.branch_id) if account.branch_id else None,
        "payroll_reference": account.payroll_reference,
        "payroll_day": account.payroll_day,
        "collection_channel": account.collection_channel,
        "reconciliation_tolerance": float(account.reconciliation_tolerance or 0),
        "payroll_contact_name": account.payroll_contact_name,
        "payroll_contact_email": account.payroll_contact_email,
        "payroll_contact_phone": account.payroll_contact_phone,
        "notes": account.notes,
        "is_active": bool(account.is_active),
    }


def employee_payload(employee: EmployerPayrollEmployee) -> dict[str, Any]:
    borrower = employee.borrower
    return {
        "id": str(employee.id),
        "account_id": str(employee.employer_account_id),
        "borrower_id": str(employee.borrower_id),
        "borrower_name": borrower_name(borrower),
        "employee_number": employee.employee_number,
        "employment_state": employee.employment_state,
        "effective_date": employee.effective_date.isoformat() if employee.effective_date else None,
        "termination_date": employee.termination_date.isoformat() if employee.termination_date else None,
        "termination_reason": employee.termination_reason,
        "last_verified_at": employee.last_verified_at.isoformat() if employee.last_verified_at else None,
    }


def deduction_payload(line: EmployerPayrollDeduction) -> dict[str, Any]:
    loan = line.loan
    borrower = line.borrower or (loan.borrower if loan else None)
    return {
        "id": str(line.id),
        "cycle_id": str(line.cycle_id),
        "borrower_id": str(line.borrower_id) if line.borrower_id else None,
        "borrower_name": borrower_name(borrower),
        "loan_id": str(line.loan_id) if line.loan_id else None,
        "loan_reference": loan.loan_reference if loan else None,
        "folio_number": line.folio_number,
        "employee_number": line.employee_number,
        "expected_amount": float(line.expected_amount or 0),
        "actual_amount": float(line.actual_amount or 0),
        "variance_amount": float(line.variance_amount or 0),
        "status": line.status,
        "rejection_code": line.rejection_code,
        "rejection_reason": line.rejection_reason,
        "employer_reference": line.employer_reference,
    }


def cycle_payload(cycle: EmployerPayrollCycle, *, include_lines: bool = False) -> dict[str, Any]:
    account = cycle.account
    result = {
        "id": str(cycle.id),
        "account_id": str(cycle.employer_account_id),
        "group_code": account.employer_group.code if account and account.employer_group else None,
        "group_name": account.employer_group.name if account and account.employer_group else None,
        "period_key": cycle.period_key,
        "scheduled_pay_date": cycle.scheduled_pay_date.isoformat(),
        "expected_amount": float(cycle.expected_amount or 0),
        "actual_amount": float(cycle.actual_amount or 0),
        "shortage_amount": float(cycle.shortage_amount or 0),
        "excess_amount": float(cycle.excess_amount or 0),
        "rejected_amount": float(cycle.rejected_amount or 0),
        "expected_line_count": cycle.expected_line_count,
        "matched_line_count": cycle.matched_line_count,
        "exception_line_count": cycle.exception_line_count,
        "status": cycle.status,
        "source": cycle.source,
        "generated_at": cycle.generated_at.isoformat() if cycle.generated_at else None,
        "received_at": cycle.received_at.isoformat() if cycle.received_at else None,
        "reconciled_at": cycle.reconciled_at.isoformat() if cycle.reconciled_at else None,
    }
    if include_lines:
        result["deductions"] = [deduction_payload(line) for line in cycle.deductions]
    return result


def build_overview(db: Session, context: TenantContext) -> dict[str, Any]:
    loans = _scoped_loans(db, context).all()
    accounts = (
        db.query(EmployerPayrollAccount)
        .options(joinedload(EmployerPayrollAccount.employer_group))
        .filter(EmployerPayrollAccount.company_id == context.company_id)
        .all()
    )
    account_by_group = {account.employer_group_id: account for account in accounts}
    relevant_group_ids = {loan.borrower.employer_group_id for loan in loans if loan.borrower and loan.borrower.employer_group_id}
    relevant_group_ids.update(account_by_group.keys())
    groups = (
        db.query(EmployerGroup)
        .filter(EmployerGroup.id.in_(relevant_group_ids))
        .all()
        if relevant_group_ids else []
    )
    group_by_id = {group.id: group for group in groups}

    employees = (
        db.query(EmployerPayrollEmployee)
        .options(joinedload(EmployerPayrollEmployee.borrower).joinedload(Borrower.user).joinedload(User.person))
        .filter(EmployerPayrollEmployee.company_id == context.company_id)
        .all()
    )
    scoped_borrower_ids = {loan.borrower_id for loan in loans}
    employees = [row for row in employees if row.borrower_id in scoped_borrower_ids]
    employees_by_account: dict[Any, list[EmployerPayrollEmployee]] = defaultdict(list)
    for row in employees:
        employees_by_account[row.employer_account_id].append(row)

    cycles_query = db.query(EmployerPayrollCycle).filter(EmployerPayrollCycle.company_id == context.company_id)
    if context.branch_id:
        cycles_query = cycles_query.filter(EmployerPayrollCycle.branch_id == context.branch_id)
    cycles = cycles_query.order_by(EmployerPayrollCycle.period_key.desc(), EmployerPayrollCycle.created_at.desc()).all()
    latest_cycle_by_account: dict[Any, EmployerPayrollCycle] = {}
    for cycle in cycles:
        latest_cycle_by_account.setdefault(cycle.employer_account_id, cycle)

    aggregate: dict[Any, dict[str, Any]] = {}
    for group_id in relevant_group_ids:
        group = group_by_id.get(group_id)
        account = account_by_group.get(group_id)
        aggregate[group_id] = {
            "employer_group_id": str(group_id),
            "group_code": group.code if group else "UNKNOWN",
            "group_name": group.name if group else "Unknown work group",
            "account": account_payload(account) if account else None,
            "borrower_ids": set(),
            "active_loan_count": 0,
            "principal_exposure": Decimal("0"),
            "outstanding_exposure": Decimal("0"),
            "overdue_exposure": Decimal("0"),
            "expected_monthly_deductions": Decimal("0"),
            "cdas_loan_count": 0,
            "cdas_expected_deductions": Decimal("0"),
            "terminated_employee_count": 0,
            "suspended_employee_count": 0,
            "latest_cycle": cycle_payload(latest_cycle_by_account[account.id]) if account and account.id in latest_cycle_by_account else None,
        }

    for loan in loans:
        borrower = loan.borrower
        group_id = borrower.employer_group_id if borrower else None
        if not group_id or group_id not in aggregate:
            continue
        item = aggregate[group_id]
        item["borrower_ids"].add(loan.borrower_id)
        if loan.status in ACTIVE_COLLECTION_STATUSES and money(loan.balance) > 0:
            expected = min(money(loan.installment_amount), money(loan.balance))
            item["active_loan_count"] += 1
            item["principal_exposure"] += money(loan.principal_amount)
            item["outstanding_exposure"] += money(loan.balance)
            item["expected_monthly_deductions"] += expected
            if loan.is_overdue:
                item["overdue_exposure"] += money(loan.balance)
            if loan.cdas_collection_enabled:
                item["cdas_loan_count"] += 1
                item["cdas_expected_deductions"] += expected

    for group_id, item in aggregate.items():
        account = account_by_group.get(group_id)
        if account:
            rows = employees_by_account.get(account.id, [])
            item["terminated_employee_count"] = sum(row.employment_state in {"terminated", "left_employer"} for row in rows)
            item["suspended_employee_count"] = sum(row.employment_state == "suspended" for row in rows)
        item["borrower_count"] = len(item.pop("borrower_ids"))
        for key in (
            "principal_exposure",
            "outstanding_exposure",
            "overdue_exposure",
            "expected_monthly_deductions",
            "cdas_expected_deductions",
        ):
            item[key] = float(money(item[key]))

    rows = sorted(aggregate.values(), key=lambda item: (item["group_code"], item["group_name"]))
    latest_cycles = list(latest_cycle_by_account.values())
    exceptions = sum(int(cycle.exception_line_count or 0) for cycle in latest_cycles)
    return {
        "summary": {
            "work_group_count": len(rows),
            "borrower_count": len(scoped_borrower_ids),
            "active_loan_count": sum(item["active_loan_count"] for item in rows),
            "outstanding_exposure": float(money(sum((Decimal(str(item["outstanding_exposure"])) for item in rows), Decimal("0")))),
            "expected_monthly_deductions": float(money(sum((Decimal(str(item["expected_monthly_deductions"])) for item in rows), Decimal("0")))),
            "overdue_exposure": float(money(sum((Decimal(str(item["overdue_exposure"])) for item in rows), Decimal("0")))),
            "terminated_employee_count": sum(item["terminated_employee_count"] for item in rows),
            "reconciliation_exception_count": exceptions,
        },
        "groups": rows,
    }


def upsert_account(
    db: Session,
    context: TenantContext,
    *,
    employer_group_id,
    payroll_reference: str | None,
    payroll_day: int | None,
    collection_channel: str,
    reconciliation_tolerance: Decimal,
    payroll_contact_name: str | None,
    payroll_contact_email: str | None,
    payroll_contact_phone: str | None,
    notes: str | None,
    is_active: bool,
) -> EmployerPayrollAccount:
    group = db.query(EmployerGroup).filter(EmployerGroup.id == employer_group_id, EmployerGroup.is_active.is_(True)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Work group was not found")
    account = db.query(EmployerPayrollAccount).filter(
        EmployerPayrollAccount.company_id == context.company_id,
        EmployerPayrollAccount.employer_group_id == employer_group_id,
    ).first()
    if not account:
        account = EmployerPayrollAccount(
            company_id=context.company_id,
            branch_id=context.branch_id,
            employer_group_id=employer_group_id,
        )
        db.add(account)
    account.payroll_reference = (payroll_reference or "").strip() or None
    account.payroll_day = payroll_day
    account.collection_channel = collection_channel.strip().lower()
    account.reconciliation_tolerance = money(reconciliation_tolerance)
    account.payroll_contact_name = (payroll_contact_name or "").strip() or None
    account.payroll_contact_email = (payroll_contact_email or "").strip() or None
    account.payroll_contact_phone = (payroll_contact_phone or "").strip() or None
    account.notes = (notes or "").strip() or None
    account.is_active = is_active
    db.commit()
    db.refresh(account)
    return account


def set_employee_state(
    db: Session,
    context: TenantContext,
    account: EmployerPayrollAccount,
    borrower: Borrower,
    *,
    employee_number: str | None,
    employment_state: str,
    effective_date: date | None,
    termination_date: date | None,
    termination_reason: str | None,
) -> EmployerPayrollEmployee:
    state = employment_state.strip().lower()
    if state not in EMPLOYMENT_STATES:
        raise HTTPException(status_code=422, detail=f"Employment state must be one of: {', '.join(sorted(EMPLOYMENT_STATES))}")
    if borrower.employer_group_id != account.employer_group_id:
        raise HTTPException(status_code=422, detail="Borrower does not belong to this work group")
    row = db.query(EmployerPayrollEmployee).filter(
        EmployerPayrollEmployee.company_id == context.company_id,
        EmployerPayrollEmployee.employer_account_id == account.id,
        EmployerPayrollEmployee.borrower_id == borrower.id,
    ).first()
    if not row:
        row = EmployerPayrollEmployee(
            company_id=context.company_id,
            employer_account_id=account.id,
            borrower_id=borrower.id,
        )
        db.add(row)
    row.employee_number = (employee_number or "").strip() or None
    row.employment_state = state
    row.effective_date = effective_date
    row.termination_date = termination_date if state in {"terminated", "left_employer"} else None
    row.termination_reason = (termination_reason or "").strip() or None
    row.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def _employee_for_borrower(db: Session, account_id, borrower_id) -> EmployerPayrollEmployee | None:
    return db.query(EmployerPayrollEmployee).filter(
        EmployerPayrollEmployee.employer_account_id == account_id,
        EmployerPayrollEmployee.borrower_id == borrower_id,
    ).first()


def _employee_number_from_loan(loan: ClientCompanyLoan, employee: EmployerPayrollEmployee | None) -> str | None:
    if employee and employee.employee_number:
        return employee.employee_number
    plan = loan.cdas_collection_plan or {}
    for key in ("employee_no", "employee_number", "employeeNo", "employeeNumber"):
        value = str(plan.get(key) or "").strip()
        if value:
            return value
    return None


def generate_cycle(
    db: Session,
    context: TenantContext,
    account: EmployerPayrollAccount,
    *,
    period_key: str,
    scheduled_pay_date: date | None,
) -> EmployerPayrollCycle:
    if not account.is_active:
        raise HTTPException(status_code=409, detail="Employer payroll account is inactive")
    pay_date = _pay_date(period_key, account.payroll_day, scheduled_pay_date)
    existing = db.query(EmployerPayrollCycle).filter(
        EmployerPayrollCycle.company_id == context.company_id,
        EmployerPayrollCycle.employer_account_id == account.id,
        EmployerPayrollCycle.period_key == period_key,
    ).first()
    if existing:
        return existing

    loans = _scoped_loans(db, context).filter(
        ClientCompanyLoan.status.in_(list(ACTIVE_COLLECTION_STATUSES)),
        ClientCompanyLoan.balance > 0,
    ).all()
    loans = [loan for loan in loans if loan.borrower and loan.borrower.employer_group_id == account.employer_group_id]

    cycle = EmployerPayrollCycle(
        company_id=context.company_id,
        employer_account_id=account.id,
        branch_id=context.branch_id,
        period_key=period_key,
        scheduled_pay_date=pay_date,
        status="open",
        source="loanhub",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(cycle)
    db.flush()

    total = Decimal("0")
    for loan in loans:
        employee = _employee_for_borrower(db, account.id, loan.borrower_id)
        expected = min(money(loan.installment_amount), money(loan.balance))
        terminated = bool(
            employee
            and employee.employment_state in {"terminated", "left_employer"}
            and (employee.termination_date is None or employee.termination_date <= pay_date)
        )
        line = EmployerPayrollDeduction(
            company_id=context.company_id,
            cycle_id=cycle.id,
            borrower_id=loan.borrower_id,
            loan_id=loan.id,
            folio_number=loan.folio_number,
            employee_number=_employee_number_from_loan(loan, employee),
            source_line_key=f"loan:{loan.id}",
            expected_amount=expected,
            actual_amount=0,
            variance_amount=-expected,
            status="terminated" if terminated else "pending",
        )
        db.add(line)
        total += expected

    cycle.expected_amount = money(total)
    cycle.expected_line_count = len(loans)
    cycle.exception_line_count = sum(1 for loan in loans if (
        (employee := _employee_for_borrower(db, account.id, loan.borrower_id))
        and employee.employment_state in {"terminated", "left_employer"}
        and (employee.termination_date is None or employee.termination_date <= pay_date)
    ))
    db.commit()
    return get_cycle(db, context, cycle.id)


def get_account(db: Session, context: TenantContext, account_id) -> EmployerPayrollAccount:
    account = (
        db.query(EmployerPayrollAccount)
        .options(joinedload(EmployerPayrollAccount.employer_group))
        .filter(
            EmployerPayrollAccount.id == account_id,
            EmployerPayrollAccount.company_id == context.company_id,
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Employer payroll account was not found")
    return account


def get_cycle(db: Session, context: TenantContext, cycle_id) -> EmployerPayrollCycle:
    query = db.query(EmployerPayrollCycle).options(
        joinedload(EmployerPayrollCycle.account).joinedload(EmployerPayrollAccount.employer_group),
        joinedload(EmployerPayrollCycle.deductions).joinedload(EmployerPayrollDeduction.loan),
        joinedload(EmployerPayrollCycle.deductions).joinedload(EmployerPayrollDeduction.borrower).joinedload(Borrower.user).joinedload(User.person),
    ).filter(
        EmployerPayrollCycle.id == cycle_id,
        EmployerPayrollCycle.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(EmployerPayrollCycle.branch_id == context.branch_id)
    cycle = query.first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Payroll cycle was not found")
    return cycle


def list_cycles(db: Session, context: TenantContext, *, account_id=None, limit: int = 100) -> list[EmployerPayrollCycle]:
    query = db.query(EmployerPayrollCycle).options(
        joinedload(EmployerPayrollCycle.account).joinedload(EmployerPayrollAccount.employer_group),
    ).filter(EmployerPayrollCycle.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(EmployerPayrollCycle.branch_id == context.branch_id)
    if account_id:
        query = query.filter(EmployerPayrollCycle.employer_account_id == account_id)
    return query.order_by(EmployerPayrollCycle.period_key.desc(), EmployerPayrollCycle.created_at.desc()).limit(limit).all()


def _normalize_header(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def import_cycle_csv(db: Session, context: TenantContext, cycle: EmployerPayrollCycle, payload: bytes) -> dict[str, Any]:
    if cycle.status == "reconciled":
        raise HTTPException(status_code=409, detail="Reconciled cycles are locked. Create a correction cycle instead of replacing history.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Payroll CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="Payroll CSV has no header row")
    field_map = {_normalize_header(name): name for name in reader.fieldnames}
    if "actual_amount" not in field_map and "amount" not in field_map:
        raise HTTPException(status_code=422, detail="Payroll CSV must include actual_amount (or amount)")
    if not any(key in field_map for key in ("folio_number", "folio", "employee_number", "employee_no")):
        raise HTTPException(status_code=422, detail="Payroll CSV must include folio_number or employee_number")

    lines = list(cycle.deductions)
    generated = [line for line in lines if line.loan_id is not None]
    for line in generated:
        line.actual_amount = 0
        line.variance_amount = -money(line.expected_amount)
        if line.status != "terminated":
            line.status = "pending"
        line.rejection_code = None
        line.rejection_reason = None
        line.employer_reference = None
        line.source_row = {}
        line.imported_at = None
    for line in [row for row in lines if row.loan_id is None]:
        db.delete(line)
    db.flush()

    by_folio = {str(line.folio_number or "").upper(): line for line in generated if line.folio_number}
    by_employee: dict[str, list[EmployerPayrollDeduction]] = defaultdict(list)
    for line in generated:
        if line.employee_number:
            by_employee[str(line.employee_number).strip().upper()].append(line)

    matched = 0
    unmatched = 0
    duplicate_matches = 0
    seen_line_ids: set[Any] = set()
    now = datetime.now(timezone.utc)
    for row_number, raw in enumerate(reader, start=2):
        row = {_normalize_header(key): str(value or "").strip() for key, value in raw.items() if key is not None}
        amount_text = row.get("actual_amount") or row.get("amount") or "0"
        actual = money(amount_text)
        folio = (row.get("folio_number") or row.get("folio") or "").upper()
        employee_no = (row.get("employee_number") or row.get("employee_no") or "").upper()
        line = by_folio.get(folio) if folio else None
        if line is None and employee_no:
            candidates = by_employee.get(employee_no, [])
            if len(candidates) == 1:
                line = candidates[0]
        if line is not None and line.id in seen_line_ids:
            duplicate_matches += 1
            line = None

        status_text = (row.get("status") or "").lower()
        rejected = status_text in {"rejected", "reject", "failed", "declined"}
        reference = row.get("reference") or row.get("employer_reference") or None
        reason = row.get("reason") or row.get("rejection_reason") or None
        code = row.get("reason_code") or row.get("rejection_code") or None

        if line is None:
            digest = hashlib.sha256(f"{row_number}:{raw}".encode("utf-8")).hexdigest()[:18]
            db.add(EmployerPayrollDeduction(
                company_id=context.company_id,
                cycle_id=cycle.id,
                borrower_id=None,
                loan_id=None,
                folio_number=folio or None,
                employee_number=employee_no or None,
                source_line_key=f"import:{row_number}:{digest}",
                expected_amount=0,
                actual_amount=actual,
                variance_amount=actual,
                status="unmatched",
                rejection_code=code,
                rejection_reason=reason or "Could not uniquely match payroll row to an expected LoanHub folio",
                employer_reference=reference,
                source_row=row,
                imported_at=now,
            ))
            unmatched += 1
            continue

        seen_line_ids.add(line.id)
        line.actual_amount = actual
        line.variance_amount = money(actual - money(line.expected_amount))
        line.rejection_code = code
        line.rejection_reason = reason
        line.employer_reference = reference
        line.source_row = row
        line.imported_at = now
        if rejected:
            line.status = "rejected"
        elif line.status == "terminated":
            line.status = "terminated"
        else:
            line.status = "received"
        matched += 1

    cycle.received_at = now
    cycle.status = "received"
    db.commit()
    cycle = get_cycle(db, context, cycle.id)
    return {
        "cycle": cycle_payload(cycle, include_lines=True),
        "import": {
            "matched_rows": matched,
            "unmatched_rows": unmatched,
            "duplicate_match_rows": duplicate_matches,
        },
    }


def reconcile_cycle(db: Session, context: TenantContext, cycle: EmployerPayrollCycle) -> EmployerPayrollCycle:
    tolerance = money(cycle.account.reconciliation_tolerance if cycle.account else 0)
    expected_total = Decimal("0")
    actual_total = Decimal("0")
    shortage_total = Decimal("0")
    excess_total = Decimal("0")
    rejected_total = Decimal("0")
    matched_count = 0
    exception_count = 0

    for line in cycle.deductions:
        expected = money(line.expected_amount)
        actual = money(line.actual_amount)
        expected_total += expected
        actual_total += actual
        variance = money(actual - expected)
        line.variance_amount = variance

        if line.loan_id is None:
            line.status = "unmatched"
        elif line.status == "terminated":
            shortage_total += max(expected - actual, Decimal("0"))
        elif line.status == "rejected":
            rejected_total += expected
            shortage_total += max(expected - actual, Decimal("0"))
        elif line.imported_at is None:
            line.status = "missing"
            shortage_total += expected
        elif abs(variance) <= tolerance:
            line.status = "matched"
            matched_count += 1
        elif variance < 0:
            line.status = "shortage"
            shortage_total += -variance
        else:
            line.status = "excess"
            excess_total += variance

        if line.status in DEDUCTION_EXCEPTION_STATUSES:
            exception_count += 1

    cycle.expected_amount = money(expected_total)
    cycle.actual_amount = money(actual_total)
    cycle.shortage_amount = money(shortage_total)
    cycle.excess_amount = money(excess_total)
    cycle.rejected_amount = money(rejected_total)
    cycle.matched_line_count = matched_count
    cycle.exception_line_count = exception_count
    cycle.status = "exception" if exception_count else "reconciled"
    cycle.reconciled_at = datetime.now(timezone.utc)
    cycle.reconciled_by_user_id = context.user.id
    db.commit()
    return get_cycle(db, context, cycle.id)


def list_exceptions(db: Session, context: TenantContext, *, limit: int = 250) -> list[EmployerPayrollDeduction]:
    query = db.query(EmployerPayrollDeduction).options(
        joinedload(EmployerPayrollDeduction.loan),
        joinedload(EmployerPayrollDeduction.borrower).joinedload(Borrower.user).joinedload(User.person),
        joinedload(EmployerPayrollDeduction.cycle),
    ).filter(
        EmployerPayrollDeduction.company_id == context.company_id,
        EmployerPayrollDeduction.status.in_(list(DEDUCTION_EXCEPTION_STATUSES)),
    )
    if context.branch_id:
        query = query.join(EmployerPayrollCycle, EmployerPayrollCycle.id == EmployerPayrollDeduction.cycle_id).filter(
            EmployerPayrollCycle.branch_id == context.branch_id
        )
    return query.order_by(EmployerPayrollDeduction.updated_at.desc()).limit(limit).all()
