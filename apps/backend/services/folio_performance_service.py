"""Company-scoped read-only folio performance snapshot.

Balances are current loan balances. Due figures are unpaid scheduled
instalment portions, not principal outstanding; receipts are successful
recorded loan-repayment transactions in the selected month.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext
from database.models.client_loan_company import ClientCompanyLoan
from database.models.payment import PaymentTransaction
from database.models.repayment import RepaymentInstallment
from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus


ZERO = Decimal("0.00")


def _money(value: object) -> float:
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def _month_bounds(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
    return start, end


def build_folio_performance(db: Session, *, context: TenantContext, today: date | None = None) -> dict:
    """Calculate aggregates without modifying a loan or exposing another tenant."""
    today = today or datetime.now(timezone.utc).date()
    month_start, month_end = _month_bounds(today)
    query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == context.company_id)
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)

    loans = query.all()
    groups = {}
    loan_groups = {}
    for loan in loans:
        code = loan.folio_group_code or "UNASSIGNED"
        g = groups.setdefault(code, {
            "group_code": code, "loan_count": 0, "active_loans": 0,
            "overdue_loans": 0, "principal": ZERO, "lifetime_paid": ZERO,
            "outstanding_balance": ZERO, "month_scheduled": ZERO,
            "month_unpaid": ZERO, "overdue_instalments": ZERO,
            "recorded_month_collections": ZERO,
        })
        loan_groups[loan.id] = code
        g["loan_count"] += 1
        status = str(getattr(loan.status, "value", loan.status) or "").lower()
        if status == "active":
            g["active_loans"] += 1
        if loan.is_overdue and Decimal(str(loan.balance or 0)) > ZERO and status not in {"completed", "rejected", "cancelled"}:
            g["overdue_loans"] += 1
        g["principal"] += Decimal(str(loan.principal_amount or 0))
        g["lifetime_paid"] += Decimal(str(loan.amount_paid or 0))
        g["outstanding_balance"] += Decimal(str(loan.balance or 0))

    ids = list(loan_groups)
    if ids:
        # Work from the existing repayment schedule; do not synthesize
        # repayment expectations from folio labels or principal amounts.
        installments = (
            db.query(RepaymentInstallment.loan_id, RepaymentInstallment.due_date,
                     RepaymentInstallment.total_due, RepaymentInstallment.paid_amount)
            .filter(RepaymentInstallment.loan_id.in_(ids),
                    RepaymentInstallment.is_superseded.is_(False),
                    RepaymentInstallment.due_date < month_end)
            .all()
        )
        for loan_id, due_date, total_due, paid_amount in installments:
            g = groups[loan_groups[loan_id]]
            unpaid = max(ZERO, Decimal(str(total_due or 0)) - Decimal(str(paid_amount or 0)))
            if month_start <= due_date < month_end:
                g["month_scheduled"] += Decimal(str(total_due or 0))
                g["month_unpaid"] += unpaid
            if due_date < today:
                g["overdue_instalments"] += unpaid

        start_dt = datetime.combine(month_start, time.min)
        end_dt = datetime.combine(month_end, time.min)
        payments = (
            db.query(PaymentTransaction.loan_id, func.sum(PaymentTransaction.amount))
            .filter(PaymentTransaction.company_id == context.company_id,
                    PaymentTransaction.loan_id.in_(ids),
                    PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT,
                    PaymentTransaction.direction == PaymentDirection.INBOUND,
                    PaymentTransaction.status == PaymentStatus.SUCCEEDED,
                    PaymentTransaction.completed_at >= start_dt,
                    PaymentTransaction.completed_at < end_dt)
            .group_by(PaymentTransaction.loan_id)
            .all()
        )
        for loan_id, amount in payments:
            groups[loan_groups[loan_id]]["recorded_month_collections"] += Decimal(str(amount or 0))

    order = {"Force": 0, "CIVIL": 1, "S/E": 2}
    result = []
    for code, group in sorted(groups.items(), key=lambda item: (order.get(item[0], 3), item[0])):
        result.append({
            key: _money(value) if isinstance(value, Decimal) else value
            for key, value in group.items()
        })
    totals = {
        key: _money(sum(Decimal(str(g[key])) for g in groups.values()))
        if key not in {"loan_count", "active_loans", "overdue_loans", "group_code"}
        else sum(g[key] for g in groups.values())
        for key in ("loan_count", "active_loans", "overdue_loans", "principal",
                    "lifetime_paid", "outstanding_balance", "month_scheduled",
                    "month_unpaid", "overdue_instalments", "recorded_month_collections")
    }
    return {
        "as_of": today.isoformat(),
        "month": month_start.strftime("%Y-%m"),
        "currency": "LSL",
        "scope": "branch" if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES else "company",
        "totals": totals,
        "groups": result,
        "definitions": {
            "month_scheduled": "Full scheduled instalment totals due during this calendar month, including amounts already paid.",
            "month_unpaid": "Unpaid portions of this month's non-superseded instalments.",
            "overdue_instalments": "Unpaid portions of non-superseded instalments due before today, including older months.",
            "recorded_month_collections": "Successful inbound loan repayment transactions completed this calendar month; other manually recorded channels may require separate reconciliation.",
            "outstanding_balance": "Current loan balances, not the amount overdue.",
        },
    }
