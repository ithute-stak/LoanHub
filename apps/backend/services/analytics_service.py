from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COLLECTIONS_ROLES,
    FINANCE_ROLES,
    HR_ROLES,
    LENDING_ROLES,
    PERFORMANCE_ROLES,
    TRANSPARENCY_ROLES,
    TenantContext,
)
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.branch import CompanyBranch
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.employee import EmployeeProfile, PerformanceGoal, PerformanceReview
from database.models.enums import (
    InstallmentStatus,
    LoanStatus,
    PaymentDirection,
    PaymentPurpose,
    PaymentStatus,
    UserRole,
)
from database.models.file_management import ManagedFile
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.payment import PaymentTransaction
from database.models.person import Person
from database.models.professional_lending import DirectLoanApplication
from database.models.repayment import RepaymentInstallment
from database.models.subscription import CompanySubscription
from database.models.system_error import SystemErrorLog
from database.models.user import User
from database.schemas.analytics import AnalyticsDashboardRead


ACTIVE_PORTFOLIO_STATUSES = {
    LoanStatus.APPROVED,
    LoanStatus.ACTIVE,
    LoanStatus.DEFAULTED,
}


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _enum(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(getattr(value, "value", value))


def _display(value: Any) -> str:
    return _enum(value).replace("_", " ").strip().title() or "Unknown"


def _safe_percent(numerator: float, denominator: float) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _change_percent(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / abs(previous)) * 100, 2)


def _metric(
    key: str,
    label: str,
    value: float,
    *,
    fmt: str = "decimal",
    previous: float | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": round(float(value), 2),
        "format": fmt,
        "previous_value": round(float(previous), 2) if previous is not None else None,
        "change_percent": _change_percent(float(value), float(previous)) if previous is not None else None,
        "description": description,
    }


def _breakdown(
    rows: Iterable[Any],
    label_getter: Callable[[Any], Any],
    value_getter: Callable[[Any], float] | None = None,
) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()
    for row in rows:
        label = _display(label_getter(row))
        counts[label] += 1
        totals[label] += float(value_getter(row)) if value_getter else 1.0
    return [
        {"label": label, "value": round(totals[label], 2), "count": counts[label]}
        for label in sorted(totals, key=lambda item: (-totals[item], item))
    ]


def _manual_breakdown(mapping: dict[str, float | int]) -> list[dict[str, Any]]:
    return [
        {"label": _display(label), "value": round(float(value), 2), "count": int(value) if float(value).is_integer() else None}
        for label, value in sorted(mapping.items(), key=lambda item: (-float(item[1]), item[0]))
    ]


def _resolve_granularity(date_from: date, date_to: date, requested: str | None) -> str:
    if requested in {"day", "week", "month"}:
        return requested
    days = (date_to - date_from).days + 1
    if days <= 45:
        return "day"
    if days <= 210:
        return "week"
    return "month"


def _period_key(value: date | datetime, granularity: str) -> date:
    current = value.date() if isinstance(value, datetime) else value
    if granularity == "week":
        return current - timedelta(days=current.weekday())
    if granularity == "month":
        return current.replace(day=1)
    return current


def _period_label(value: date, granularity: str) -> str:
    if granularity == "month":
        return value.strftime("%b %Y")
    if granularity == "week":
        return f"Week of {value.strftime('%d %b')}"
    return value.strftime("%d %b")


def _period_keys(date_from: date, date_to: date, granularity: str) -> list[date]:
    keys: list[date] = []
    current = _period_key(date_from, granularity)
    end = _period_key(date_to, granularity)
    while current <= end:
        keys.append(current)
        if granularity == "month":
            month_index = current.month
            year = current.year + month_index // 12
            month = month_index % 12 + 1
            current = date(year, month, 1)
        elif granularity == "week":
            current += timedelta(days=7)
        else:
            current += timedelta(days=1)
    return keys


def _empty_series(date_from: date, date_to: date, granularity: str, fields: Iterable[str]) -> dict[date, dict[str, float]]:
    return {key: {field: 0.0 for field in fields} for key in _period_keys(date_from, date_to, granularity)}


def _serialize_series(series: dict[date, dict[str, float]], granularity: str) -> list[dict[str, Any]]:
    return [
        {
            "period": _period_label(period, granularity),
            "values": {key: round(value, 2) for key, value in values.items()},
        }
        for period, values in sorted(series.items())
    ]


def _within(value: date | datetime | None, date_from: date, date_to: date) -> bool:
    if value is None:
        return False
    current = value.date() if isinstance(value, datetime) else value
    return date_from <= current <= date_to


def _date_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    return datetime.combine(date_from, time.min), datetime.combine(date_to + timedelta(days=1), time.min)


def _previous_period(date_from: date, date_to: date) -> tuple[date, date]:
    duration = (date_to - date_from).days + 1
    previous_to = date_from - timedelta(days=1)
    return previous_to - timedelta(days=duration - 1), previous_to


def _age_band(dob: date | None) -> str:
    if not dob:
        return "Unknown"
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 25:
        return "18–24"
    if age < 35:
        return "25–34"
    if age < 45:
        return "35–44"
    if age < 55:
        return "45–54"
    if age < 65:
        return "55–64"
    return "65+"


def _loan_size_band(amount: float) -> str:
    if amount < 1_000:
        return "Below LSL 1,000"
    if amount < 5_000:
        return "LSL 1,000–4,999"
    if amount < 10_000:
        return "LSL 5,000–9,999"
    if amount < 25_000:
        return "LSL 10,000–24,999"
    return "LSL 25,000+"


def _term_band(term: int) -> str:
    if term <= 1:
        return "1 period"
    if term <= 3:
        return "2–3 periods"
    if term <= 6:
        return "4–6 periods"
    if term <= 12:
        return "7–12 periods"
    return "13+ periods"


def _arrears_band(days: int) -> str:
    if days <= 7:
        return "1–7 days"
    if days <= 30:
        return "8–30 days"
    if days <= 60:
        return "31–60 days"
    if days <= 90:
        return "61–90 days"
    return "90+ days"


def _query_payments(
    db: Session,
    *,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    date_from: date,
    date_to: date,
    borrower_id: UUID | None = None,
) -> list[PaymentTransaction]:
    start, end = _date_bounds(date_from, date_to)
    query = db.query(PaymentTransaction).filter(PaymentTransaction.created_at >= start, PaymentTransaction.created_at < end)
    if company_id:
        query = query.filter(PaymentTransaction.company_id == company_id)
    if borrower_id:
        query = query.filter(PaymentTransaction.borrower_id == borrower_id)
    if branch_id:
        query = query.join(ClientCompanyLoan, PaymentTransaction.loan_id == ClientCompanyLoan.id).filter(ClientCompanyLoan.branch_id == branch_id)
    return query.all()


def _permissions_for_company(role: UserRole) -> dict[str, bool]:
    oversight_roles = {
        UserRole.COMPANY_OWNER,
        UserRole.COMPANY_ADMIN,
        UserRole.AUDITOR,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.RISK_MANAGER,
    }
    return {
        "overview": True,
        "lending": role in LENDING_ROLES or role in oversight_roles,
        "collections": role in COLLECTIONS_ROLES or role in FINANCE_ROLES or role in oversight_roles,
        "finance": role in FINANCE_ROLES or role in {UserRole.BRANCH_MANAGER, *oversight_roles},
        "marketplace": role in LENDING_ROLES or role in oversight_roles,
        "people": role in HR_ROLES or role in PERFORMANCE_ROLES,
        "operations": role in TRANSPARENCY_ROLES,
    }


def _core_company_data(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    date_from: date,
    date_to: date,
    granularity: str,
    permissions: dict[str, bool],
) -> dict[str, Any]:
    previous_from, previous_to = _previous_period(date_from, date_to)
    start, end = _date_bounds(date_from, date_to)
    previous_start, previous_end = _date_bounds(previous_from, previous_to)

    loan_query = db.query(ClientCompanyLoan).options(joinedload(ClientCompanyLoan.borrower).joinedload(Borrower.user).joinedload(User.person)).filter(ClientCompanyLoan.company_id == company_id)
    if branch_id:
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == branch_id)
    loans = loan_query.all()
    period_loans = [row for row in loans if _within(row.created_at, date_from, date_to)]
    previous_loans = [row for row in loans if _within(row.created_at, previous_from, previous_to)]

    payments = _query_payments(db, company_id=company_id, branch_id=branch_id, date_from=date_from, date_to=date_to)
    previous_payments = _query_payments(db, company_id=company_id, branch_id=branch_id, date_from=previous_from, date_to=previous_to)

    installment_query = db.query(RepaymentInstallment).join(ClientCompanyLoan, RepaymentInstallment.loan_id == ClientCompanyLoan.id).filter(ClientCompanyLoan.company_id == company_id)
    if branch_id:
        installment_query = installment_query.filter(ClientCompanyLoan.branch_id == branch_id)
    installments = installment_query.all()
    period_installments = [row for row in installments if date_from <= row.due_date <= date_to]

    active_loans = [row for row in loans if row.status in ACTIVE_PORTFOLIO_STATUSES]
    outstanding = sum(_number(row.balance) for row in active_loans)
    principal_portfolio = sum(_number(row.principal_amount) for row in active_loans)
    overdue_loans = [row for row in active_loans if row.is_overdue or row.status == LoanStatus.DEFAULTED]
    overdue_exposure = sum(_number(row.balance) for row in overdue_loans)

    successful = [row for row in payments if row.status == PaymentStatus.SUCCEEDED]
    previous_successful = [row for row in previous_payments if row.status == PaymentStatus.SUCCEEDED]
    collections = [row for row in successful if row.purpose == PaymentPurpose.LOAN_REPAYMENT and row.direction == PaymentDirection.INBOUND]
    disbursements = [row for row in successful if row.purpose == PaymentPurpose.LOAN_DISBURSEMENT and row.direction == PaymentDirection.OUTBOUND]
    previous_collections = [row for row in previous_successful if row.purpose == PaymentPurpose.LOAN_REPAYMENT and row.direction == PaymentDirection.INBOUND]
    previous_disbursements = [row for row in previous_successful if row.purpose == PaymentPurpose.LOAN_DISBURSEMENT and row.direction == PaymentDirection.OUTBOUND]
    collected_value = sum(_number(row.amount) for row in collections)
    disbursed_value = sum(_number(row.amount) for row in disbursements)
    previous_collected = sum(_number(row.amount) for row in previous_collections)
    previous_disbursed = sum(_number(row.amount) for row in previous_disbursements)
    due_value = sum(_number(row.total_due) for row in period_installments)
    paid_against_due = sum(min(_number(row.paid_amount), _number(row.total_due)) for row in period_installments)
    collection_rate = _safe_percent(paid_against_due, due_value)
    arrears_rate = _safe_percent(overdue_exposure, outstanding)
    period_principal = sum(_number(row.principal_amount) for row in period_loans)
    previous_principal = sum(_number(row.principal_amount) for row in previous_loans)

    metrics = [
        _metric("active_loans", "Active portfolio", len(active_loans), fmt="integer", description="Approved, active and defaulted facilities still on the books."),
        _metric("outstanding_balance", "Outstanding balance", outstanding, fmt="money", description="Current balance across the active portfolio."),
        _metric("originated_principal", "Originated principal", period_principal, fmt="money", previous=previous_principal, description="Principal created inside the selected period."),
        _metric("collections", "Collections", collected_value, fmt="money", previous=previous_collected, description="Successful loan repayments in the selected period."),
        _metric("disbursements", "Disbursements", disbursed_value, fmt="money", previous=previous_disbursed, description="Successful loan payouts in the selected period."),
        _metric("net_cashflow", "Net lending cash flow", collected_value - disbursed_value, fmt="money", previous=previous_collected - previous_disbursed, description="Collections less loan disbursements."),
        _metric("collection_rate", "Collection rate", collection_rate, fmt="percent", description="Amount paid against instalments due in the selected period."),
        _metric("arrears_rate", "Arrears exposure", arrears_rate, fmt="percent", description="Overdue/defaulted balance as a share of active outstanding balance."),
        _metric("average_loan_size", "Average loan size", period_principal / len(period_loans) if period_loans else 0, fmt="money", description="Average principal for loans created in the selected period."),
        _metric("active_borrowers", "Active borrowers", len({row.borrower_id for row in active_loans}), fmt="integer", description="Distinct borrowers with an active portfolio balance."),
    ]

    volume = _empty_series(date_from, date_to, granularity, ["loan_count", "principal", "approved_count"])
    for row in period_loans:
        key = _period_key(row.created_at, granularity)
        volume[key]["loan_count"] += 1
        volume[key]["principal"] += _number(row.principal_amount)
        if row.approved_at:
            volume[key]["approved_count"] += 1

    cashflow = _empty_series(date_from, date_to, granularity, ["collections", "disbursements", "net"])
    for row in successful:
        event_date = row.completed_at or row.created_at
        key = _period_key(event_date, granularity)
        if row.purpose == PaymentPurpose.LOAN_REPAYMENT and row.direction == PaymentDirection.INBOUND:
            cashflow[key]["collections"] += _number(row.amount)
        if row.purpose == PaymentPurpose.LOAN_DISBURSEMENT and row.direction == PaymentDirection.OUTBOUND:
            cashflow[key]["disbursements"] += _number(row.amount)
    for values in cashflow.values():
        values["net"] = values["collections"] - values["disbursements"]

    repayment = _empty_series(date_from, date_to, granularity, ["due", "paid", "overdue"])
    for row in period_installments:
        key = _period_key(row.due_date, granularity)
        due = _number(row.total_due)
        paid = _number(row.paid_amount)
        repayment[key]["due"] += due
        repayment[key]["paid"] += paid
        if row.status == InstallmentStatus.OVERDUE or (row.due_date < date.today() and paid < due):
            repayment[key]["overdue"] += max(due - paid, 0)

    breakdowns: dict[str, list[dict[str, Any]]] = {
        "loan_status": _breakdown(loans, lambda row: row.status),
        "risk_level": _breakdown(active_loans, lambda row: row.risk_level, lambda row: _number(row.balance)),
        "calculation_method": _breakdown(loans, lambda row: row.calculation_method, lambda row: _number(row.principal_amount)),
        "origination_channel": _breakdown(loans, lambda row: row.origination_channel, lambda row: _number(row.principal_amount)),
        "loan_size_bands": _breakdown(loans, lambda row: _loan_size_band(_number(row.principal_amount)), lambda row: _number(row.principal_amount)),
        "term_bands": _breakdown(loans, lambda row: _term_band(int(row.repayment_period or 0)), lambda row: _number(row.principal_amount)),
        "installment_status": _breakdown(installments, lambda row: row.status, lambda row: _number(row.total_due)),
        "payment_method": _breakdown(successful, lambda row: row.payment_method, lambda row: _number(row.amount)),
        "payment_status": _breakdown(payments, lambda row: row.status, lambda row: _number(row.amount)),
        "payment_purpose": _breakdown(payments, lambda row: row.purpose, lambda row: _number(row.amount)),
    }

    arrears: dict[str, float] = defaultdict(float)
    today = date.today()
    for row in installments:
        due = _number(row.total_due)
        paid = _number(row.paid_amount)
        if row.due_date >= today or paid >= due:
            continue
        arrears[_arrears_band((today - row.due_date).days)] += due - paid
    breakdowns["arrears_aging"] = _manual_breakdown(arrears)

    branch_rows: list[dict[str, Any]] = []
    if not branch_id:
        branches = db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id).all()
        for branch in branches:
            branch_loans = [row for row in loans if row.branch_id == branch.id]
            branch_outstanding = sum(_number(row.balance) for row in branch_loans if row.status in ACTIVE_PORTFOLIO_STATUSES)
            branch_paid = sum(_number(row.amount_paid) for row in branch_loans)
            branch_due = sum(_number(row.total_repayable) for row in branch_loans)
            branch_rows.append({
                "label": branch.name,
                "value": round(branch_outstanding, 2),
                "count": len(branch_loans),
                "secondary_value": round(branch_paid, 2),
                "extra": {
                    "collection_rate": _safe_percent(branch_paid, branch_due),
                    "overdue_count": len([row for row in branch_loans if row.is_overdue or row.status == LoanStatus.DEFAULTED]),
                    "principal": round(sum(_number(row.principal_amount) for row in branch_loans), 2),
                },
            })
        breakdowns["branch_performance"] = sorted(branch_rows, key=lambda row: (-row["value"], row["label"]))

    unique_borrowers: dict[UUID, Borrower] = {}
    for loan in loans:
        if loan.borrower:
            unique_borrowers[loan.borrower.id] = loan.borrower
    borrowers = list(unique_borrowers.values())
    breakdowns["borrower_district"] = _breakdown(borrowers, lambda row: row.user.person.district if row.user and row.user.person else "unknown")
    breakdowns["borrower_gender"] = _breakdown(borrowers, lambda row: row.user.person.gender if row.user and row.user.person else "unknown")
    breakdowns["borrower_age"] = _breakdown(borrowers, lambda row: _age_band(row.user.person.date_of_birth if row.user and row.user.person else None))
    breakdowns["borrower_employment"] = _breakdown(borrowers, lambda row: row.employment_status)

    applications_series = _empty_series(date_from, date_to, granularity, ["submitted", "approved", "rejected", "offers", "accepted_offers"])
    if permissions["marketplace"]:
        direct_query = db.query(DirectLoanApplication).filter(DirectLoanApplication.company_id == company_id, DirectLoanApplication.created_at >= start, DirectLoanApplication.created_at < end)
        offer_query = db.query(LoanOffer).filter(LoanOffer.company_id == company_id, LoanOffer.created_at >= start, LoanOffer.created_at < end)
        if branch_id:
            direct_query = direct_query.filter(DirectLoanApplication.branch_id == branch_id)
            offer_query = offer_query.filter(LoanOffer.branch_id == branch_id)
        applications = direct_query.all()
        offers = offer_query.all()
        for row in applications:
            key = _period_key(row.created_at, granularity)
            applications_series[key]["submitted"] += 1
            if row.status == "approved":
                applications_series[key]["approved"] += 1
            if row.status == "rejected":
                applications_series[key]["rejected"] += 1
        for row in offers:
            key = _period_key(row.created_at, granularity)
            applications_series[key]["offers"] += 1
            if _enum(row.status) == "accepted":
                applications_series[key]["accepted_offers"] += 1
        breakdowns["application_status"] = _breakdown(applications, lambda row: row.status)
        breakdowns["offer_status"] = _breakdown(offers, lambda row: row.status)
        breakdowns["marketplace_funnel"] = _manual_breakdown({
            "Applications": len(applications),
            "Offers": len(offers),
            "Approved applications": len([row for row in applications if row.status == "approved"]),
            "Accepted offers": len([row for row in offers if _enum(row.status) == "accepted"]),
            "Loans created": len(period_loans),
        })

    series: dict[str, list[dict[str, Any]]] = {
        "loan_volume": _serialize_series(volume, granularity),
        "cashflow": _serialize_series(cashflow, granularity),
        "repayments": _serialize_series(repayment, granularity),
        "applications": _serialize_series(applications_series, granularity),
    }

    if permissions["finance"]:
        journal_query = db.query(JournalEntry).filter(JournalEntry.company_id == company_id, JournalEntry.entry_date >= date_from, JournalEntry.entry_date <= date_to)
        if branch_id:
            journal_query = journal_query.filter(JournalEntry.branch_id == branch_id)
        journals = journal_query.all()
        accounting = _empty_series(date_from, date_to, granularity, ["debits", "credits", "posted_entries"])
        for row in journals:
            key = _period_key(row.entry_date, granularity)
            accounting[key]["debits"] += _number(row.total_debit)
            accounting[key]["credits"] += _number(row.total_credit)
            if row.status == "posted":
                accounting[key]["posted_entries"] += 1
        series["accounting"] = _serialize_series(accounting, granularity)
        account_query = db.query(AccountingAccount).filter(AccountingAccount.company_id == company_id)
        if branch_id:
            account_query = account_query.filter(or_(AccountingAccount.branch_id == branch_id, AccountingAccount.branch_id.is_(None)))
        accounts = account_query.all()
        breakdowns["account_types"] = _breakdown(accounts, lambda row: row.account_type)

    if permissions["people"]:
        staff_query = db.query(CompanyStaff).filter(CompanyStaff.company_id == company_id)
        employee_query = db.query(EmployeeProfile).filter(EmployeeProfile.company_id == company_id)
        review_query = db.query(PerformanceReview).filter(PerformanceReview.company_id == company_id, PerformanceReview.created_at >= start, PerformanceReview.created_at < end)
        goal_query = db.query(PerformanceGoal).filter(PerformanceGoal.company_id == company_id)
        if branch_id:
            staff_query = staff_query.filter(CompanyStaff.branch_id == branch_id)
            employee_query = employee_query.filter(EmployeeProfile.branch_id == branch_id)
            review_query = review_query.filter(PerformanceReview.branch_id == branch_id)
            goal_query = goal_query.filter(PerformanceGoal.branch_id == branch_id)
        staff = staff_query.all()
        employees = employee_query.all()
        reviews = review_query.all()
        goals = goal_query.all()
        breakdowns["staff_roles"] = _breakdown(staff, lambda row: row.role)
        breakdowns["departments"] = _breakdown(employees, lambda row: row.department or "Unassigned")
        breakdowns["employment_status"] = _breakdown(employees, lambda row: row.employment_status)
        breakdowns["performance_ratings"] = _breakdown(reviews, lambda row: row.rating, lambda row: _number(row.overall_score))
        breakdowns["goal_status"] = _breakdown(goals, lambda row: row.status)
        performance_series = _empty_series(date_from, date_to, granularity, ["average_score", "review_count"])
        score_totals: dict[date, float] = defaultdict(float)
        for row in reviews:
            key = _period_key(row.created_at, granularity)
            score_totals[key] += _number(row.overall_score)
            performance_series[key]["review_count"] += 1
        for key, values in performance_series.items():
            values["average_score"] = score_totals[key] / values["review_count"] if values["review_count"] else 0
        series["performance"] = _serialize_series(performance_series, granularity)

    heatmaps: dict[str, list[dict[str, Any]]] = {}
    if permissions["operations"]:
        file_query = db.query(ManagedFile).filter(ManagedFile.company_id == company_id, ManagedFile.created_at >= start, ManagedFile.created_at < end, ManagedFile.is_deleted.is_(False))
        audit_query = db.query(AuditLog).filter(AuditLog.company_id == company_id, AuditLog.created_at >= start, AuditLog.created_at < end)
        if branch_id:
            file_query = file_query.filter(or_(ManagedFile.branch_id == branch_id, ManagedFile.branch_id.is_(None)))
            audit_query = audit_query.filter(or_(AuditLog.branch_id == branch_id, AuditLog.branch_id.is_(None)))
        files = file_query.all()
        audits = audit_query.all()
        breakdowns["file_categories"] = _breakdown(files, lambda row: row.category, lambda row: _number(row.size_bytes))
        breakdowns["file_visibility"] = _breakdown(files, lambda row: row.visibility)
        breakdowns["audit_actions"] = _breakdown(audits, lambda row: row.action)
        breakdowns["audit_entities"] = _breakdown(audits, lambda row: row.entity_type or row.table_name or "unknown")
        breakdowns["audit_severity"] = _breakdown(audits, lambda row: row.severity)
        file_series = _empty_series(date_from, date_to, granularity, ["uploads", "megabytes"])
        audit_series = _empty_series(date_from, date_to, granularity, ["events", "failures", "critical"])
        heat: Counter[tuple[str, int]] = Counter()
        for row in files:
            key = _period_key(row.created_at, granularity)
            file_series[key]["uploads"] += 1
            file_series[key]["megabytes"] += _number(row.size_bytes) / (1024 * 1024)
        for row in audits:
            key = _period_key(row.created_at, granularity)
            audit_series[key]["events"] += 1
            if row.status == "failure":
                audit_series[key]["failures"] += 1
            if row.severity == "critical":
                audit_series[key]["critical"] += 1
            heat[(row.created_at.strftime("%a"), row.created_at.hour)] += 1
        series["files"] = _serialize_series(file_series, granularity)
        series["audit"] = _serialize_series(audit_series, granularity)
        heatmaps["activity"] = [
            {"day": day, "hour": hour, "value": count}
            for (day, hour), count in sorted(heat.items(), key=lambda item: (item[0][0], item[0][1]))
        ]

    scatter = {
        "loan_pricing": [
            {
                "label": row.loan_reference,
                "x": _number(row.interest_rate),
                "y": float(row.repayment_period or 0),
                "size": _number(row.principal_amount),
                "extra": {"status": _enum(row.status), "method": row.calculation_method},
            }
            for row in loans[:500]
        ]
    }

    insights: list[dict[str, Any]] = []
    if arrears_rate >= 20:
        insights.append({"title": "High arrears exposure", "message": f"{arrears_rate:.1f}% of the active outstanding balance is overdue or defaulted.", "tone": "critical", "action_url": "/company/loans"})
    elif arrears_rate >= 8:
        insights.append({"title": "Arrears need attention", "message": f"Arrears exposure is {arrears_rate:.1f}%. Prioritise the oldest unpaid instalments.", "tone": "warning", "action_url": "/company/loans"})
    else:
        insights.append({"title": "Portfolio quality is controlled", "message": f"Arrears exposure is {arrears_rate:.1f}% of outstanding balance.", "tone": "positive", "action_url": "/company/loans"})
    if collection_rate < 70 and due_value > 0:
        insights.append({"title": "Collections are below target", "message": f"Only {collection_rate:.1f}% of instalments due in this period have been collected.", "tone": "critical", "action_url": "/company/cashier"})
    elif due_value > 0:
        insights.append({"title": "Collection performance", "message": f"The collection rate for the selected period is {collection_rate:.1f}%.", "tone": "positive" if collection_rate >= 90 else "neutral", "action_url": "/company/payments"})
    if collected_value - disbursed_value < 0:
        insights.append({"title": "Net lending cash flow is negative", "message": "Disbursements exceeded collections during the selected period. Confirm treasury funding and expected receipts.", "tone": "warning", "action_url": "/company/expense-management"})
    if branch_rows:
        worst = max(branch_rows, key=lambda row: row["extra"].get("overdue_count", 0))
        if worst["extra"].get("overdue_count", 0):
            insights.append({"title": "Branch collections focus", "message": f"{worst['label']} has the highest overdue-loan count ({worst['extra']['overdue_count']}).", "tone": "warning", "action_url": "/company/branches"})

    if not permissions["lending"]:
        metrics = [item for item in metrics if item["key"] not in {"originated_principal", "average_loan_size"}]
        series.pop("loan_volume", None)
        scatter.pop("loan_pricing", None)
        for key in ("risk_level", "calculation_method", "origination_channel", "loan_size_bands", "term_bands"):
            breakdowns.pop(key, None)
    if not permissions["collections"]:
        metrics = [item for item in metrics if item["key"] not in {"collection_rate", "arrears_rate"}]
        series.pop("repayments", None)
        for key in ("installment_status", "arrears_aging"):
            breakdowns.pop(key, None)
    if not permissions["finance"]:
        metrics = [item for item in metrics if item["key"] not in {"collections", "disbursements", "net_cashflow"}]
        series.pop("cashflow", None)
        for key in ("payment_method", "payment_status", "payment_purpose", "account_types"):
            breakdowns.pop(key, None)
    if not permissions["people"]:
        for key in ("borrower_district", "borrower_gender", "borrower_age", "borrower_employment", "staff_roles", "departments", "employment_status", "performance_ratings", "goal_status"):
            breakdowns.pop(key, None)
        series.pop("performance", None)
    if not permissions["operations"]:
        for key in ("file_categories", "file_visibility", "audit_actions", "audit_entities", "audit_severity"):
            breakdowns.pop(key, None)
        series.pop("files", None)
        series.pop("audit", None)
        heatmaps.clear()

    return {
        "metrics": metrics,
        "series": series,
        "breakdowns": breakdowns,
        "scatter": scatter,
        "heatmaps": heatmaps,
        "insights": insights,
    }


def build_company_analytics(
    db: Session,
    *,
    context: TenantContext,
    date_from: date,
    date_to: date,
    granularity: str | None = None,
    branch_id: UUID | None = None,
) -> AnalyticsDashboardRead:
    if not context.company_id:
        raise ValueError("Company context is required")
    resolved_branch = branch_id
    if context.branch_id:
        if branch_id and branch_id != context.branch_id:
            raise PermissionError("This role cannot access another branch")
        resolved_branch = context.branch_id
    resolved_granularity = _resolve_granularity(date_from, date_to, granularity)
    permissions = _permissions_for_company(context.role)
    payload = _core_company_data(
        db,
        company_id=context.company_id,
        branch_id=resolved_branch,
        date_from=date_from,
        date_to=date_to,
        granularity=resolved_granularity,
        permissions=permissions,
    )
    return AnalyticsDashboardRead(
        scope={
            "scope": "company",
            "company_id": str(context.company_id),
            "branch_id": str(resolved_branch) if resolved_branch else None,
            "role": context.role.value,
            "date_from": date_from,
            "date_to": date_to,
            "granularity": resolved_granularity,
        },
        permissions=permissions,
        generated_at=datetime.now(timezone.utc),
        **payload,
    )


def build_platform_analytics(
    db: Session,
    *,
    current_user: User,
    date_from: date,
    date_to: date,
    granularity: str | None = None,
) -> AnalyticsDashboardRead:
    resolved_granularity = _resolve_granularity(date_from, date_to, granularity)
    previous_from, previous_to = _previous_period(date_from, date_to)
    start, end = _date_bounds(date_from, date_to)
    previous_start, previous_end = _date_bounds(previous_from, previous_to)

    companies = db.query(LoanCompany).all()
    branches = db.query(CompanyBranch).all()
    staff = db.query(CompanyStaff).all()
    borrowers = db.query(Borrower).options(joinedload(Borrower.user).joinedload(User.person)).all()
    employees = db.query(EmployeeProfile).all()
    reviews = db.query(PerformanceReview).filter(PerformanceReview.created_at >= start, PerformanceReview.created_at < end).all()
    goals = db.query(PerformanceGoal).all()
    requests = db.query(LoanRequest).filter(LoanRequest.created_at >= start, LoanRequest.created_at < end).all()
    previous_requests = db.query(LoanRequest).filter(LoanRequest.created_at >= previous_start, LoanRequest.created_at < previous_end).all()
    offers = db.query(LoanOffer).filter(LoanOffer.created_at >= start, LoanOffer.created_at < end).all()
    loans = db.query(ClientCompanyLoan).options(joinedload(ClientCompanyLoan.company)).all()
    period_loans = [row for row in loans if _within(row.created_at, date_from, date_to)]
    previous_loans = [row for row in loans if _within(row.created_at, previous_from, previous_to)]
    payments = _query_payments(db, date_from=date_from, date_to=date_to)
    previous_payments = _query_payments(db, date_from=previous_from, date_to=previous_to)
    subscriptions = db.query(CompanySubscription).all()
    platform_journals = db.query(JournalEntry).filter(
        JournalEntry.scope_type == "platform",
        JournalEntry.entry_date >= date_from,
        JournalEntry.entry_date <= date_to,
    ).all()
    platform_accounts = db.query(AccountingAccount).filter(AccountingAccount.scope_type == "platform").all()

    successful = [row for row in payments if row.status == PaymentStatus.SUCCEEDED]
    previous_successful = [row for row in previous_payments if row.status == PaymentStatus.SUCCEEDED]
    platform_revenue_purposes = {
        PaymentPurpose.SUBSCRIPTION,
        PaymentPurpose.MARKETPLACE_UNLOCK,
        PaymentPurpose.BORROW_REQUEST_FEE,
        PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
        PaymentPurpose.PLATFORM_FEE,
        PaymentPurpose.PLATFORM_TRANSACTION_CHARGE,
    }
    platform_revenue = sum(_number(row.amount) for row in successful if row.purpose in platform_revenue_purposes and row.direction == PaymentDirection.INBOUND)
    previous_platform_revenue = sum(_number(row.amount) for row in previous_successful if row.purpose in platform_revenue_purposes and row.direction == PaymentDirection.INBOUND)
    active_loans = [row for row in loans if row.status in ACTIVE_PORTFOLIO_STATUSES]
    outstanding = sum(_number(row.balance) for row in active_loans)
    period_principal = sum(_number(row.principal_amount) for row in period_loans)
    previous_principal = sum(_number(row.principal_amount) for row in previous_loans)
    payment_value = sum(_number(row.amount) for row in successful)
    previous_payment_value = sum(_number(row.amount) for row in previous_successful)

    metrics = [
        _metric("companies", "Registered companies", len(companies), fmt="integer", description="All lender tenants registered on LoanHub."),
        _metric("approved_companies", "Approved companies", len([row for row in companies if _enum(row.status) == "approved"]), fmt="integer"),
        _metric("borrowers", "Borrowers", len(borrowers), fmt="integer", description="Registered borrower profiles."),
        _metric("loan_requests", "Loan requests", len(requests), fmt="integer", previous=len(previous_requests), description="Marketplace requests created in the selected period."),
        _metric("originated_principal", "Originated principal", period_principal, fmt="money", previous=previous_principal),
        _metric("outstanding_balance", "Platform outstanding", outstanding, fmt="money", description="Outstanding balances across all lending companies."),
        _metric("successful_payment_value", "Successful transaction value", payment_value, fmt="money", previous=previous_payment_value),
        _metric("platform_revenue", "Platform revenue", platform_revenue, fmt="money", previous=previous_platform_revenue),
        _metric("active_loans", "Active portfolio", len(active_loans), fmt="integer"),
        _metric("branches", "Company branches", len(branches), fmt="integer"),
    ]

    company_growth = _empty_series(date_from, date_to, resolved_granularity, ["companies", "approved"])
    request_series = _empty_series(date_from, date_to, resolved_granularity, ["requests", "accepted", "offers"])
    loan_series = _empty_series(date_from, date_to, resolved_granularity, ["loans", "principal"])
    payment_series = _empty_series(date_from, date_to, resolved_granularity, ["transaction_value", "platform_revenue", "failures"])
    for row in companies:
        if _within(row.created_at, date_from, date_to):
            key = _period_key(row.created_at, resolved_granularity)
            company_growth[key]["companies"] += 1
            if _enum(row.status) == "approved":
                company_growth[key]["approved"] += 1
    for row in requests:
        key = _period_key(row.created_at, resolved_granularity)
        request_series[key]["requests"] += 1
        if _enum(row.status) == "accepted":
            request_series[key]["accepted"] += 1
    for row in offers:
        key = _period_key(row.created_at, resolved_granularity)
        request_series[key]["offers"] += 1
    for row in period_loans:
        key = _period_key(row.created_at, resolved_granularity)
        loan_series[key]["loans"] += 1
        loan_series[key]["principal"] += _number(row.principal_amount)
    for row in payments:
        key = _period_key(row.completed_at or row.created_at, resolved_granularity)
        if row.status == PaymentStatus.SUCCEEDED:
            payment_series[key]["transaction_value"] += _number(row.amount)
            if row.purpose in platform_revenue_purposes and row.direction == PaymentDirection.INBOUND:
                payment_series[key]["platform_revenue"] += _number(row.amount)
        elif row.status == PaymentStatus.FAILED:
            payment_series[key]["failures"] += 1

    accounting_series = _empty_series(date_from, date_to, resolved_granularity, ["debits", "credits", "posted_entries"])
    for row in platform_journals:
        key = _period_key(row.entry_date, resolved_granularity)
        accounting_series[key]["debits"] += _number(row.total_debit)
        accounting_series[key]["credits"] += _number(row.total_credit)
        if row.status == "posted":
            accounting_series[key]["posted_entries"] += 1

    performance_series = _empty_series(date_from, date_to, resolved_granularity, ["average_score", "review_count"])
    review_scores: dict[date, float] = defaultdict(float)
    for row in reviews:
        key = _period_key(row.created_at, resolved_granularity)
        review_scores[key] += _number(row.overall_score)
        performance_series[key]["review_count"] += 1
    for key, values in performance_series.items():
        values["average_score"] = review_scores[key] / values["review_count"] if values["review_count"] else 0

    company_performance: list[dict[str, Any]] = []
    for company in companies:
        company_loans = [row for row in loans if row.company_id == company.id]
        company_outstanding = sum(_number(row.balance) for row in company_loans if row.status in ACTIVE_PORTFOLIO_STATUSES)
        company_paid = sum(_number(row.amount_paid) for row in company_loans)
        company_total = sum(_number(row.total_repayable) for row in company_loans)
        company_performance.append({
            "label": company.name,
            "value": round(company_outstanding, 2),
            "count": len(company_loans),
            "secondary_value": round(company_paid, 2),
            "extra": {
                "collection_rate": _safe_percent(company_paid, company_total),
                "overdue_count": len([row for row in company_loans if row.is_overdue or row.status == LoanStatus.DEFAULTED]),
                "status": _enum(company.status),
            },
        })

    files = db.query(ManagedFile).filter(ManagedFile.created_at >= start, ManagedFile.created_at < end, ManagedFile.is_deleted.is_(False)).all()
    audits = db.query(AuditLog).filter(AuditLog.created_at >= start, AuditLog.created_at < end).all()
    errors = db.query(SystemErrorLog).filter(SystemErrorLog.last_seen_at >= start, SystemErrorLog.last_seen_at < end).all()
    error_series = _empty_series(date_from, date_to, resolved_granularity, ["errors", "occurrences", "resolved"])
    for row in errors:
        key = _period_key(row.last_seen_at, resolved_granularity)
        error_series[key]["errors"] += 1
        error_series[key]["occurrences"] += row.occurrence_count
        if row.is_resolved:
            error_series[key]["resolved"] += 1

    audit_heat: Counter[tuple[str, int]] = Counter()
    audit_series = _empty_series(date_from, date_to, resolved_granularity, ["events", "failures", "critical"])
    for row in audits:
        key = _period_key(row.created_at, resolved_granularity)
        audit_series[key]["events"] += 1
        if row.status == "failure":
            audit_series[key]["failures"] += 1
        if row.severity == "critical":
            audit_series[key]["critical"] += 1
        audit_heat[(row.created_at.strftime("%a"), row.created_at.hour)] += 1

    breakdowns = {
        "company_status": _breakdown(companies, lambda row: row.status),
        "company_district": _breakdown(companies, lambda row: row.district or "Unknown"),
        "subscription_status": _breakdown(subscriptions, lambda row: row.status, lambda row: _number(row.amount)),
        "subscription_plan": _breakdown(subscriptions, lambda row: row.plan_name, lambda row: _number(row.amount)),
        "request_status": _breakdown(requests, lambda row: row.status, lambda row: _number(row.requested_amount)),
        "offer_status": _breakdown(offers, lambda row: row.status, lambda row: _number(row.approved_amount)),
        "loan_status": _breakdown(loans, lambda row: row.status, lambda row: _number(row.balance)),
        "risk_level": _breakdown(active_loans, lambda row: row.risk_level, lambda row: _number(row.balance)),
        "payment_method": _breakdown(successful, lambda row: row.payment_method, lambda row: _number(row.amount)),
        "payment_status": _breakdown(payments, lambda row: row.status, lambda row: _number(row.amount)),
        "payment_purpose": _breakdown(payments, lambda row: row.purpose, lambda row: _number(row.amount)),
        "staff_roles": _breakdown(staff, lambda row: row.role),
        "borrower_district": _breakdown(borrowers, lambda row: row.user.person.district if row.user and row.user.person else "Unknown"),
        "borrower_gender": _breakdown(borrowers, lambda row: row.user.person.gender if row.user and row.user.person else "Unknown"),
        "borrower_age": _breakdown(borrowers, lambda row: _age_band(row.user.person.date_of_birth if row.user and row.user.person else None)),
        "borrower_employment": _breakdown(borrowers, lambda row: row.employment_status),
        "departments": _breakdown(employees, lambda row: row.department or "Unassigned"),
        "employment_status": _breakdown(employees, lambda row: row.employment_status),
        "performance_ratings": _breakdown(reviews, lambda row: row.rating, lambda row: _number(row.overall_score)),
        "goal_status": _breakdown(goals, lambda row: row.status),
        "account_types": _breakdown(platform_accounts, lambda row: row.account_type),
        "company_performance": sorted(company_performance, key=lambda row: (-row["value"], row["label"])),
        "file_categories": _breakdown(files, lambda row: row.category, lambda row: _number(row.size_bytes)),
        "file_visibility": _breakdown(files, lambda row: row.visibility),
        "audit_actions": _breakdown(audits, lambda row: row.action),
        "audit_entities": _breakdown(audits, lambda row: row.entity_type or row.table_name or "Unknown"),
        "audit_severity": _breakdown(audits, lambda row: row.severity),
        "error_severity": _breakdown(errors, lambda row: row.severity, lambda row: row.occurrence_count),
        "marketplace_funnel": _manual_breakdown({
            "Requests": len(requests),
            "Offers": len(offers),
            "Accepted requests": len([row for row in requests if _enum(row.status) == "accepted"]),
            "Loans created": len(period_loans),
        }),
    }

    insights: list[dict[str, Any]] = []
    pending_companies = len([row for row in companies if _enum(row.status) == "pending"])
    failed_value = sum(_number(row.amount) for row in payments if row.status == PaymentStatus.FAILED)
    if pending_companies:
        insights.append({"title": "Company approvals pending", "message": f"{pending_companies} lender tenant(s) are awaiting platform review.", "tone": "warning", "action_url": "/superadmin/companies"})
    if failed_value:
        insights.append({"title": "Failed payment value", "message": f"LSL {failed_value:,.2f} in attempted payments failed during the selected period.", "tone": "warning", "action_url": "/superadmin/payments"})
    unresolved_errors = sum(1 for row in errors if not row.is_resolved)
    if unresolved_errors:
        insights.append({"title": "Unresolved system incidents", "message": f"{unresolved_errors} error fingerprint(s) remain unresolved.", "tone": "critical", "action_url": "/superadmin/system-errors"})
    if platform_revenue > previous_platform_revenue:
        insights.append({"title": "Platform revenue increased", "message": f"Revenue is {_change_percent(platform_revenue, previous_platform_revenue) or 0:.1f}% above the previous comparable period.", "tone": "positive", "action_url": "/superadmin/accounting"})

    role = current_user.role
    permissions = {
        "overview": True,
        "lending": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS, UserRole.PLATFORM_AUDITOR, UserRole.PLATFORM_COMPLIANCE},
        "collections": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_FINANCE, UserRole.PLATFORM_AUDITOR, UserRole.PLATFORM_COMPLIANCE},
        "finance": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_FINANCE, UserRole.PLATFORM_AUDITOR, UserRole.PLATFORM_COMPLIANCE},
        "marketplace": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS, UserRole.PLATFORM_AUDITOR, UserRole.PLATFORM_COMPLIANCE},
        "people": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS, UserRole.PLATFORM_AUDITOR},
        "operations": role in {UserRole.SUPERADMIN, UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUPPORT, UserRole.PLATFORM_OPERATIONS, UserRole.PLATFORM_AUDITOR, UserRole.PLATFORM_COMPLIANCE},
    }

    platform_series = {
        "company_growth": _serialize_series(company_growth, resolved_granularity),
        "marketplace": _serialize_series(request_series, resolved_granularity),
        "loan_volume": _serialize_series(loan_series, resolved_granularity),
        "payments": _serialize_series(payment_series, resolved_granularity),
        "accounting": _serialize_series(accounting_series, resolved_granularity),
        "performance": _serialize_series(performance_series, resolved_granularity),
        "audit": _serialize_series(audit_series, resolved_granularity),
        "errors": _serialize_series(error_series, resolved_granularity),
    }
    platform_breakdowns = breakdowns
    platform_scatter = {
        "company_portfolio": [
            {
                "label": row["label"],
                "x": float(row["extra"].get("collection_rate", 0)),
                "y": float(row["value"]),
                "size": float(row["count"] or 0),
                "extra": row["extra"],
            }
            for row in company_performance
        ]
    }
    platform_heatmaps = {
        "activity": [
            {"day": day, "hour": hour, "value": count}
            for (day, hour), count in sorted(audit_heat.items(), key=lambda item: (item[0][0], item[0][1]))
        ]
    }
    if not permissions["lending"]:
        metrics = [item for item in metrics if item["key"] not in {"loan_requests", "originated_principal", "outstanding_balance", "active_loans"}]
        for key in ("marketplace", "loan_volume"):
            platform_series.pop(key, None)
        for key in ("request_status", "offer_status", "loan_status", "risk_level", "marketplace_funnel", "company_performance"):
            platform_breakdowns.pop(key, None)
        platform_scatter.clear()
    if not permissions["finance"]:
        metrics = [item for item in metrics if item["key"] not in {"successful_payment_value", "platform_revenue"}]
        platform_series.pop("payments", None)
        platform_series.pop("accounting", None)
        for key in ("subscription_status", "subscription_plan", "payment_method", "payment_status", "payment_purpose", "account_types"):
            platform_breakdowns.pop(key, None)
    if not permissions["people"]:
        platform_series.pop("performance", None)
        for key in ("staff_roles", "borrower_district", "borrower_gender", "borrower_age", "borrower_employment", "departments", "employment_status", "performance_ratings", "goal_status"):
            platform_breakdowns.pop(key, None)
    if not permissions["operations"]:
        for key in ("file_categories", "file_visibility", "audit_actions", "audit_entities", "audit_severity", "error_severity"):
            platform_breakdowns.pop(key, None)
        for key in ("audit", "errors"):
            platform_series.pop(key, None)
        platform_heatmaps.clear()

    return AnalyticsDashboardRead(
        scope={
            "scope": "platform",
            "role": current_user.role.value,
            "date_from": date_from,
            "date_to": date_to,
            "granularity": resolved_granularity,
        },
        metrics=metrics,
        series=platform_series,
        breakdowns=platform_breakdowns,
        scatter=platform_scatter,
        heatmaps=platform_heatmaps,
        insights=insights,
        permissions=permissions,
        generated_at=datetime.now(timezone.utc),
    )


def build_borrower_analytics(
    db: Session,
    *,
    current_user: User,
    date_from: date,
    date_to: date,
    granularity: str | None = None,
) -> AnalyticsDashboardRead:
    borrower = db.query(Borrower).filter(Borrower.user_id == current_user.id).first()
    if not borrower:
        raise LookupError("Borrower profile was not found")
    resolved_granularity = _resolve_granularity(date_from, date_to, granularity)
    previous_from, previous_to = _previous_period(date_from, date_to)
    start, end = _date_bounds(date_from, date_to)
    previous_start, previous_end = _date_bounds(previous_from, previous_to)

    requests = db.query(LoanRequest).filter(LoanRequest.borrower_id == borrower.id).all()
    loans = db.query(ClientCompanyLoan).options(joinedload(ClientCompanyLoan.company)).filter(ClientCompanyLoan.borrower_id == borrower.id).all()
    payments = _query_payments(db, borrower_id=borrower.id, date_from=date_from, date_to=date_to)
    previous_payments = _query_payments(db, borrower_id=borrower.id, date_from=previous_from, date_to=previous_to)
    installments = db.query(RepaymentInstallment).join(ClientCompanyLoan, RepaymentInstallment.loan_id == ClientCompanyLoan.id).filter(ClientCompanyLoan.borrower_id == borrower.id).all()

    active_loans = [row for row in loans if row.status in ACTIVE_PORTFOLIO_STATUSES]
    outstanding = sum(_number(row.balance) for row in active_loans)
    successful_repayments = [row for row in payments if row.status == PaymentStatus.SUCCEEDED and row.purpose == PaymentPurpose.LOAN_REPAYMENT]
    previous_repayments = [row for row in previous_payments if row.status == PaymentStatus.SUCCEEDED and row.purpose == PaymentPurpose.LOAN_REPAYMENT]
    repaid = sum(_number(row.amount) for row in successful_repayments)
    previous_repaid = sum(_number(row.amount) for row in previous_repayments)
    due_installments = [row for row in installments if date_from <= row.due_date <= date_to]
    due_value = sum(_number(row.total_due) for row in due_installments)
    paid_value = sum(min(_number(row.paid_amount), _number(row.total_due)) for row in due_installments)
    on_time_rate = _safe_percent(paid_value, due_value)

    metrics = [
        _metric("active_loans", "Active loans", len(active_loans), fmt="integer"),
        _metric("outstanding", "Outstanding balance", outstanding, fmt="money"),
        _metric("repayments", "Repayments made", repaid, fmt="money", previous=previous_repaid),
        _metric("payment_rate", "Payment completion", on_time_rate, fmt="percent", description="Amount paid against instalments due during the selected period."),
        _metric("requests", "Loan requests", len(requests), fmt="integer"),
        _metric("total_borrowed", "Total principal borrowed", sum(_number(row.principal_amount) for row in loans), fmt="money"),
    ]

    balance_series = _empty_series(date_from, date_to, resolved_granularity, ["principal", "repayments", "instalments_due"])
    for row in loans:
        if _within(row.created_at, date_from, date_to):
            key = _period_key(row.created_at, resolved_granularity)
            balance_series[key]["principal"] += _number(row.principal_amount)
    for row in successful_repayments:
        key = _period_key(row.completed_at or row.created_at, resolved_granularity)
        balance_series[key]["repayments"] += _number(row.amount)
    for row in due_installments:
        key = _period_key(row.due_date, resolved_granularity)
        balance_series[key]["instalments_due"] += _number(row.total_due)

    request_series = _empty_series(date_from, date_to, resolved_granularity, ["requests", "accepted", "offers"])
    period_requests = [row for row in requests if _within(row.created_at, date_from, date_to)]
    request_ids = [row.id for row in period_requests]
    offers = db.query(LoanOffer).filter(LoanOffer.loan_request_id.in_(request_ids)).all() if request_ids else []
    for row in period_requests:
        key = _period_key(row.created_at, resolved_granularity)
        request_series[key]["requests"] += 1
        if _enum(row.status) == "accepted":
            request_series[key]["accepted"] += 1
    for row in offers:
        key = _period_key(row.created_at, resolved_granularity)
        request_series[key]["offers"] += 1

    loan_progress: list[dict[str, Any]] = []
    for row in loans:
        total = _number(row.total_repayable)
        paid = _number(row.amount_paid)
        loan_progress.append({
            "label": row.loan_reference,
            "value": round(_safe_percent(paid, total), 2),
            "count": int(row.repayment_period or 0),
            "secondary_value": round(_number(row.balance), 2),
            "extra": {"company": row.company.name if row.company else "Loan company", "status": _enum(row.status)},
        })

    overdue_amount = sum(max(_number(row.total_due) - _number(row.paid_amount), 0) for row in installments if row.due_date < date.today() and _number(row.paid_amount) < _number(row.total_due))
    insights: list[dict[str, Any]] = []
    if overdue_amount:
        insights.append({"title": "Overdue instalments", "message": f"You have LSL {overdue_amount:,.2f} overdue. Contact the lender early if you need assistance.", "tone": "critical", "action_url": "/borrower/loans"})
    elif active_loans:
        insights.append({"title": "Repayment account is current", "message": "No overdue instalment balance is recorded across your active loans.", "tone": "positive", "action_url": "/borrower/loans"})
    open_requests = len([row for row in requests if _enum(row.status) in {"open", "submitted", "offered", "under_review"}])
    if open_requests:
        insights.append({"title": "Open marketplace requests", "message": f"{open_requests} request(s) are still open or under review.", "tone": "neutral", "action_url": "/borrower/requests"})

    return AnalyticsDashboardRead(
        scope={
            "scope": "borrower",
            "borrower_id": str(borrower.id),
            "role": current_user.role.value,
            "date_from": date_from,
            "date_to": date_to,
            "granularity": resolved_granularity,
        },
        metrics=metrics,
        series={
            "borrower_cashflow": _serialize_series(balance_series, resolved_granularity),
            "borrower_requests": _serialize_series(request_series, resolved_granularity),
        },
        breakdowns={
            "request_status": _breakdown(requests, lambda row: row.status, lambda row: _number(row.requested_amount)),
            "loan_status": _breakdown(loans, lambda row: row.status, lambda row: _number(row.balance)),
            "lender_exposure": _breakdown(loans, lambda row: row.company.name if row.company else "Loan company", lambda row: _number(row.balance)),
            "payment_method": _breakdown(successful_repayments, lambda row: row.payment_method, lambda row: _number(row.amount)),
            "installment_status": _breakdown(installments, lambda row: row.status, lambda row: _number(row.total_due)),
            "loan_progress": sorted(loan_progress, key=lambda row: (row["value"], row["label"])),
        },
        scatter={
            "loan_terms": [
                {
                    "label": row.loan_reference,
                    "x": _number(row.interest_rate),
                    "y": float(row.repayment_period or 0),
                    "size": _number(row.principal_amount),
                    "extra": {"company": row.company.name if row.company else "Loan company"},
                }
                for row in loans
            ]
        },
        heatmaps={},
        insights=insights,
        permissions={"overview": True, "lending": True, "collections": True, "finance": False, "marketplace": True, "people": False, "operations": False},
        generated_at=datetime.now(timezone.utc),
    )
