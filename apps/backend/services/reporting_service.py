from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.audit_log import AuditLog
from database.models.branch import CompanyBranch
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.employee import EmployeeProfile, PerformanceGoal, PerformanceReview
from database.models.enums import (
    LoanStatus,
    PaymentMethod,
    PaymentStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.payment import PaymentTransaction
from database.models.reporting import GeneratedReport, ReportSchedule
from database.models.treasury import BranchDailyLedger, BranchDailySubmission, BranchOpeningSource, TreasuryEntry
from services.file_service import store_bytes
from services.pdf_design_system import money_text, safe_text


def money(value: Any) -> float:
    return round(float(value or 0), 2)


def report_reference() -> str:
    return f"RPT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def period_for_frequency(frequency: str, reference: date | None = None) -> tuple[date, date]:
    today = reference or datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()
    if frequency == "daily":
        day = today - timedelta(days=1)
        return day, day
    if frequency == "weekly":
        end = today - timedelta(days=today.weekday() + 1)
        return end - timedelta(days=6), end
    if frequency == "monthly":
        first_this_month = today.replace(day=1)
        end = first_this_month - timedelta(days=1)
        return end.replace(day=1), end
    end = date(today.year - 1, 12, 31)
    return date(end.year, 1, 1), end


def next_run_for_frequency(frequency: str, now: datetime | None = None) -> datetime:
    """Return the next local-midnight schedule stored as UTC."""
    local_zone = ZoneInfo(settings.APP_TIMEZONE)
    current_utc = now or datetime.now(timezone.utc)
    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=timezone.utc)
    current = current_utc.astimezone(local_zone)
    base = datetime.combine(current.date(), time(hour=0), tzinfo=local_zone)

    if frequency == "daily":
        candidate = base + timedelta(days=1)
    elif frequency == "weekly":
        days = (0 - current.weekday()) % 7
        candidate = base + timedelta(days=days)
        if candidate <= current:
            candidate += timedelta(days=7)
    elif frequency == "monthly":
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        candidate = datetime(year, month, 1, 0, tzinfo=local_zone)
    else:
        candidate = datetime(current.year + 1, 1, 1, 0, tzinfo=local_zone)

    return candidate.astimezone(timezone.utc)


def _apply_scope(query, model, company_id=None, branch_id=None):
    if company_id is not None and hasattr(model, "company_id"):
        query = query.filter(model.company_id == company_id)
    if branch_id is not None and hasattr(model, "branch_id"):
        query = query.filter(model.branch_id == branch_id)
    return query


def _financial_metrics(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    company_id=None,
    branch_id=None,
) -> dict[str, Any]:
    key = f"company:{company_id}" if company_id else "platform"
    query = (
        db.query(
            AccountingAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalLine, JournalLine.account_id == AccountingAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .filter(
            AccountingAccount.scope_key == key,
            JournalEntry.status == "posted",
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
        )
    )
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)

    totals = {
        "asset": Decimal("0"),
        "liability": Decimal("0"),
        "equity": Decimal("0"),
        "revenue": Decimal("0"),
        "expense": Decimal("0"),
    }
    for account_type, debit, credit in query.group_by(
        AccountingAccount.account_type
    ).all():
        debit = Decimal(debit)
        credit = Decimal(credit)
        if account_type in {"revenue", "liability", "equity"}:
            totals[account_type] = credit - debit
        else:
            totals[account_type] = debit - credit

    return {
        "accounting_revenue": money(totals["revenue"]),
        "accounting_expenses": money(totals["expense"]),
        "accounting_net_profit": money(
            totals["revenue"] - totals["expense"]
        ),
        "accounting_assets": money(totals["asset"]),
        "accounting_liabilities": money(totals["liability"]),
        "accounting_equity": money(totals["equity"]),
    }



def _treasury_metrics(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    company_id=None,
    branch_id=None,
) -> dict[str, Any]:
    """Operational money-book metrics used by saved accounting reports.

    Voided, rejected, and pending entries are excluded. For branch daily
    submissions, only the latest sequence per financial day is counted so a
    corrected resubmission does not double-count the same branch date.
    """
    start_dt = datetime.combine(period_start, time.min)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min)
    posted_statuses = {
        TreasuryEntryApprovalStatus.POSTED,
        TreasuryEntryApprovalStatus.APPROVED,
    }

    entry_query = db.query(TreasuryEntry).filter(
        TreasuryEntry.occurred_at >= start_dt,
        TreasuryEntry.occurred_at < end_dt,
        TreasuryEntry.is_voided.is_(False),
        TreasuryEntry.approval_status.in_(posted_statuses),
    )
    if company_id is not None:
        entry_query = entry_query.filter(TreasuryEntry.company_id == company_id)
    if branch_id is not None:
        entry_query = entry_query.filter(TreasuryEntry.branch_id == branch_id)
    entries = entry_query.all()

    source_query = (
        db.query(BranchOpeningSource)
        .join(BranchDailyLedger, BranchDailyLedger.id == BranchOpeningSource.daily_ledger_id)
        .filter(
            BranchDailyLedger.business_date >= period_start,
            BranchDailyLedger.business_date <= period_end,
            BranchOpeningSource.is_confirmed.is_(True),
            BranchOpeningSource.is_voided.is_(False),
        )
    )
    if company_id is not None:
        source_query = source_query.filter(BranchOpeningSource.company_id == company_id)
    if branch_id is not None:
        source_query = source_query.filter(BranchOpeningSource.branch_id == branch_id)
    sources = source_query.all()

    submission_query = db.query(BranchDailySubmission).filter(
        BranchDailySubmission.business_date >= period_start,
        BranchDailySubmission.business_date <= period_end,
    )
    if company_id is not None:
        submission_query = submission_query.filter(BranchDailySubmission.company_id == company_id)
    if branch_id is not None:
        submission_query = submission_query.filter(BranchDailySubmission.branch_id == branch_id)
    latest_submissions: dict[object, BranchDailySubmission] = {}
    for row in submission_query.order_by(
        BranchDailySubmission.daily_ledger_id,
        BranchDailySubmission.sequence_number.asc(),
    ).all():
        latest_submissions[row.daily_ledger_id] = row
    submissions = list(latest_submissions.values())

    money_in = sum(
        (Decimal(str(row.amount or 0)) for row in entries if row.direction == TreasuryDirection.MONEY_IN),
        Decimal("0"),
    )
    money_out = sum(
        (Decimal(str(row.amount or 0)) for row in entries if row.direction == TreasuryDirection.MONEY_OUT),
        Decimal("0"),
    )
    expenses = sum(
        (Decimal(str(row.amount or 0)) for row in entries if row.entry_type == TreasuryEntryType.EXPENSE),
        Decimal("0"),
    )
    collections = sum(
        (Decimal(str(row.amount or 0)) for row in entries if row.entry_type == TreasuryEntryType.LOAN_COLLECTION),
        Decimal("0"),
    )
    disbursements = sum(
        (Decimal(str(row.amount or 0)) for row in entries if row.entry_type == TreasuryEntryType.LOAN_DISBURSEMENT),
        Decimal("0"),
    )
    opening_total = sum((Decimal(str(row.amount or 0)) for row in sources), Decimal("0"))
    owner_opening = sum(
        (Decimal(str(row.amount or 0)) for row in sources if str(row.source_type.value) == "owner_contribution"),
        Decimal("0"),
    )
    variance_total = sum((abs(Decimal(str(row.variance_amount or 0))) for row in submissions), Decimal("0"))

    result: dict[str, Any] = {
        "treasury_opening_sources": money(opening_total),
        "treasury_owner_contributions": money(owner_opening),
        "treasury_money_in": money(money_in),
        "treasury_money_out": money(money_out),
        "treasury_net_movement": money(money_in - money_out),
        "treasury_operating_expenses": money(expenses),
        "treasury_loan_collections": money(collections),
        "treasury_loan_disbursements": money(disbursements),
        "branch_submission_days": len(submissions),
        "automatic_branch_submissions": len([row for row in submissions if row.is_automatic]),
        "branch_submissions_with_variance": len([row for row in submissions if Decimal(str(row.variance_amount or 0)) != 0]),
        "absolute_branch_variance": money(variance_total),
    }

    for method in PaymentMethod:
        method_in = sum(
            (Decimal(str(row.amount or 0)) for row in entries if row.payment_method == method and row.direction == TreasuryDirection.MONEY_IN),
            Decimal("0"),
        )
        method_out = sum(
            (Decimal(str(row.amount or 0)) for row in entries if row.payment_method == method and row.direction == TreasuryDirection.MONEY_OUT),
            Decimal("0"),
        )
        if method_in or method_out:
            prefix = f"channel_{method.value}"
            result[f"{prefix}_money_in"] = money(method_in)
            result[f"{prefix}_money_out"] = money(method_out)
            result[f"{prefix}_net"] = money(method_in - method_out)
    return result

def collect_metrics(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    company_id=None,
    branch_id=None,
) -> dict[str, Any]:
    start_dt = datetime.combine(period_start, time.min)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min)

    company_query = db.query(func.count(LoanCompany.id))
    if company_id:
        company_query = company_query.filter(LoanCompany.id == company_id)

    branches = _apply_scope(
        db.query(func.count(CompanyBranch.id)),
        CompanyBranch,
        company_id,
        branch_id,
    ).scalar() or 0
    staff = (
        _apply_scope(
            db.query(func.count(CompanyStaff.id)),
            CompanyStaff,
            company_id,
            branch_id,
        )
        .filter(CompanyStaff.is_active.is_(True))
        .scalar()
        or 0
    )
    employees = _apply_scope(
        db.query(func.count(EmployeeProfile.id)),
        EmployeeProfile,
        company_id,
        branch_id,
    ).scalar() or 0

    request_query = db.query(LoanRequest).filter(
        LoanRequest.created_at >= start_dt,
        LoanRequest.created_at < end_dt,
    )
    if company_id:
        request_query = (
            request_query
            .join(LoanOffer, LoanOffer.loan_request_id == LoanRequest.id)
            .filter(LoanOffer.company_id == company_id)
            .distinct()
        )
        if branch_id:
            request_query = request_query.filter(LoanOffer.branch_id == branch_id)

    offer_query = _apply_scope(
        db.query(LoanOffer),
        LoanOffer,
        company_id,
        branch_id,
    ).filter(
        LoanOffer.created_at >= start_dt,
        LoanOffer.created_at < end_dt,
    )
    loan_query = _apply_scope(
        db.query(ClientCompanyLoan),
        ClientCompanyLoan,
        company_id,
        branch_id,
    )
    payment_query = _apply_scope(
        db.query(PaymentTransaction),
        PaymentTransaction,
        company_id,
        branch_id,
    ).filter(
        PaymentTransaction.created_at >= start_dt,
        PaymentTransaction.created_at < end_dt,
    )

    review_query = _apply_scope(
        db.query(PerformanceReview),
        PerformanceReview,
        company_id,
        branch_id,
    ).filter(
        PerformanceReview.period_end >= period_start,
        PerformanceReview.period_start <= period_end,
    )
    goal_query = _apply_scope(
        db.query(PerformanceGoal),
        PerformanceGoal,
        company_id,
        branch_id,
    ).filter(
        PerformanceGoal.period_end >= period_start,
        PerformanceGoal.period_start <= period_end,
    )

    loans = loan_query.all()
    payments = payment_query.all()
    requests = request_query.all()
    offers = offer_query.all()
    reviews = review_query.all()
    goals = goal_query.all()
    successful_payments = [
        item
        for item in payments
        if item.status == PaymentStatus.SUCCEEDED
    ]

    active_loans = [
        item
        for item in loans
        if item.status in {LoanStatus.ACTIVE, LoanStatus.APPROVED}
    ]
    completed_loans = [
        item for item in loans if item.status == LoanStatus.COMPLETED
    ]
    overdue_loans = [item for item in loans if item.is_overdue]
    completed_goals = [
        item
        for item in goals
        if item.status == "completed"
        or (
            Decimal(str(item.target_value or 0)) > 0
            and Decimal(str(item.current_value or 0))
            >= Decimal(str(item.target_value or 0))
        )
    ]

    metrics = {
        "companies": int(company_query.scalar() or 0),
        "branches": int(branches),
        "active_staff": int(staff),
        "employee_profiles": int(employees),
        "loan_requests_engaged": len(requests),
        "offers_created": len(offers),
        "offers_accepted": len([
            item
            for item in offers
            if str(
                item.status.value
                if hasattr(item.status, "value")
                else item.status
            ) == "accepted"
        ]),
        "active_loans": len(active_loans),
        "completed_loans": len(completed_loans),
        "overdue_loans": len(overdue_loans),
        "principal_portfolio": money(sum(
            (item.principal_amount for item in loans),
            Decimal("0"),
        )),
        "outstanding_balance": money(sum(
            (item.balance for item in loans),
            Decimal("0"),
        )),
        "amount_paid": money(sum(
            (item.amount_paid for item in loans),
            Decimal("0"),
        )),
        "successful_transactions": len(successful_payments),
        "successful_payment_value": money(sum(
            (item.amount for item in successful_payments),
            Decimal("0"),
        )),
        "failed_transactions": len([
            item for item in payments if item.status == PaymentStatus.FAILED
        ]),
        "request_to_offer_rate": round(
            (len(offers) / len(requests) * 100) if requests else 0,
            2,
        ),
        "portfolio_overdue_rate": round(
            (len(overdue_loans) / len(loans) * 100) if loans else 0,
            2,
        ),
        "performance_reviews": len(reviews),
        "average_performance_score": round(
            sum(float(item.overall_score or 0) for item in reviews)
            / len(reviews)
            if reviews
            else 0,
            2,
        ),
        "performance_goals": len(goals),
        "goal_completion_rate": round(
            (len(completed_goals) / len(goals) * 100) if goals else 0,
            2,
        ),
    }
    audit_query = _apply_scope(
        db.query(AuditLog),
        AuditLog,
        company_id,
        branch_id,
    ).filter(
        AuditLog.created_at >= start_dt,
        AuditLog.created_at < end_dt,
    )
    audit_rows = audit_query.all()
    metrics.update({
        'audit_events': len(audit_rows),
        'failed_audit_events': len([item for item in audit_rows if item.status == 'failure']),
        'critical_audit_events': len([item for item in audit_rows if item.severity == 'critical']),
        'unique_audit_actors': len({item.user_id for item in audit_rows if item.user_id}),
    })

    metrics.update(_financial_metrics(
        db,
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
    ))
    metrics.update(_treasury_metrics(
        db,
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
    ))
    return metrics


def _scope_name(db: Session, company_id=None, branch_id=None) -> str:
    if branch_id:
        branch = db.query(CompanyBranch).filter(CompanyBranch.id == branch_id).first()
        if branch:
            return f"{branch.name} Branch"
    if company_id:
        company = db.query(LoanCompany).filter(LoanCompany.id == company_id).first()
        if company:
            return company.name
    return "LoanHub Platform"




def _asset_path(configured_value: str) -> Path | None:
    configured = Path(configured_value).expanduser()
    if not configured.is_absolute():
        configured = Path(__file__).resolve().parents[1] / configured
    return configured if configured.exists() else None


def _product_logo_path() -> Path | None:
    return _asset_path(settings.LOANHUB_LOGO_PATH)


def _developer_logo_path() -> Path | None:
    return _asset_path(settings.DEVELOPER_LOGO_PATH)

def _report_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float, Decimal)):
        amount_tokens = (
            "balance", "value", "paid", "portfolio", "revenue", "expense",
            "profit", "assets", "liabilities", "equity", "money", "opening",
            "contribution", "variance", "collection", "disbursement", "fees",
        )
        if any(token in key for token in amount_tokens):
            return money_text(value)
        if "rate" in key or "score" in key or "percent" in key:
            return f"{float(value):,.2f}%"
        return f"{int(value):,}" if float(value).is_integer() else f"{float(value):,.2f}"
    return safe_text(value)


def _accounting_insights(metrics: dict[str, Any]) -> list[tuple[str, str, str]]:
    insights: list[tuple[str, str, str]] = []
    revenue = float(metrics.get("accounting_revenue", 0) or 0)
    expenses = float(metrics.get("accounting_expenses", 0) or 0)
    profit = float(metrics.get("accounting_net_profit", 0) or 0)
    assets = float(metrics.get("accounting_assets", 0) or 0)
    liabilities = float(metrics.get("accounting_liabilities", 0) or 0)
    equity = float(metrics.get("accounting_equity", 0) or 0)
    net_movement = float(metrics.get("treasury_net_movement", 0) or 0)
    overdue_rate = float(metrics.get("portfolio_overdue_rate", 0) or 0)
    variance = float(metrics.get("absolute_branch_variance", 0) or 0)

    if revenue or expenses or profit:
        if profit > 0:
            margin = (profit / revenue * 100) if revenue else 0
            insights.append(("Operating result", f"The period produced a net accounting profit of {money_text(profit)}. The implied margin is {margin:,.1f}% of recognised revenue.", "green"))
        elif profit < 0:
            insights.append(("Operating result", f"The period produced an accounting loss of {money_text(abs(profit))}. Management should review expense drivers, pricing and collection performance.", "red"))
        else:
            insights.append(("Operating result", "Recognised accounting revenue and expenses produced a break-even result for the period.", "amber"))

    equation_gap = assets - liabilities - equity
    if abs(equation_gap) <= 0.05:
        insights.append(("Accounting equation", f"Assets of {money_text(assets)} reconcile to liabilities plus equity. The accounting equation is balanced within rounding tolerance.", "green"))
    else:
        insights.append(("Accounting equation exception", f"Assets differ from liabilities plus equity by {money_text(equation_gap)}. Review unposted journals, opening balances and account classifications.", "red"))

    if net_movement > 0:
        insights.append(("Cash movement", f"Operational money movement was positive by {money_text(net_movement)} after recorded inflows and outflows.", "green"))
    elif net_movement < 0:
        insights.append(("Cash movement", f"Operational money movement was negative by {money_text(abs(net_movement))}. Confirm that disbursements and operating costs are supported by available funding.", "amber"))

    if overdue_rate >= 20:
        insights.append(("Portfolio risk", f"The overdue-loan rate is {overdue_rate:,.1f}%, which requires focused collections and credit-quality review.", "red"))
    elif overdue_rate > 0:
        insights.append(("Portfolio risk", f"The overdue-loan rate is {overdue_rate:,.1f}%. Continue monitoring arrears and payment arrangements.", "amber"))
    else:
        insights.append(("Portfolio risk", "No overdue loans are recorded in the scoped portfolio for this report snapshot.", "green"))

    if variance > 0:
        insights.append(("Branch reconciliation", f"Absolute branch closing variance totals {money_text(variance)}. Each affected branch submission should be investigated and resolved.", "red"))
    return insights


def build_pdf(
    *,
    db: Session,
    company: LoanCompany | None,
    title: str,
    reference: str,
    scope_name: str,
    period_start: date,
    period_end: date,
    metrics: dict[str, Any],
    report_type: str,
) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from services.pdf_design_system import (
        DocumentContext,
        build_document,
        callout,
        detail_card,
        document_styles,
        generated_timestamp,
        hero_block,
        metric_grid,
        money_text,
        progress_bar,
        safe_text,
        section,
        timeline_card,
        two_card_row,
    )

    styles = document_styles()
    story: list[Any] = []
    story.extend(hero_block(
        title,
        "A management-ready report that explains financial position, money movement, portfolio quality, operations and control exceptions.",
        reference,
        status="completed",
        styles=styles,
    ))

    period_card = detail_card(
        "Report scope",
        [
            ("Scope", scope_name),
            ("Report type", report_type.replace("_", " ").title()),
            ("Period start", period_start.strftime("%d %B %Y")),
            ("Period end", period_end.strftime("%d %B %Y")),
            ("Reference", reference),
        ],
        tone="blue",
    )
    control_card = detail_card(
        "Document control",
        [
            ("Generated", generated_timestamp().replace("Generated ", "")),
            ("Source", "Posted LoanHub operational and accounting records"),
            ("Currency", "Lesotho loti (LSL)"),
            ("Status", "Final generated snapshot"),
            ("Review", "Management and authorised finance users"),
        ],
        tone="slate",
    )
    story.append(two_card_row(period_card, control_card))
    story.append(Spacer(1, 4 * mm))

    story.extend(section("Executive financial summary", "The first view focuses on the figures management normally needs before reading operational detail.", styles=styles))
    story.append(metric_grid([
        ("Accounting revenue", money_text(metrics.get("accounting_revenue", 0)), "Posted revenue for the period", "green"),
        ("Accounting expenses", money_text(metrics.get("accounting_expenses", 0)), "Posted expenses for the period", "red"),
        ("Net profit / loss", money_text(metrics.get("accounting_net_profit", 0)), "Revenue less expenses", "green" if float(metrics.get("accounting_net_profit", 0) or 0) >= 0 else "red"),
        ("Treasury net movement", money_text(metrics.get("treasury_net_movement", 0)), "Money in less money out", "teal" if float(metrics.get("treasury_net_movement", 0) or 0) >= 0 else "amber"),
        ("Outstanding portfolio", money_text(metrics.get("outstanding_balance", 0)), "Current borrower balances", "amber"),
        ("Successful payment value", money_text(metrics.get("successful_payment_value", 0)), "Completed transactions in the period", "blue"),
    ], columns=2, styles=styles))

    story.extend(section("Statement of financial position", "A concise accounting view of what the scope owns, owes and has accumulated as equity.", styles=styles))
    story.append(metric_grid([
        ("Assets", money_text(metrics.get("accounting_assets", 0)), "Debit-balance resources", "blue"),
        ("Liabilities", money_text(metrics.get("accounting_liabilities", 0)), "Obligations to external parties", "amber"),
        ("Equity", money_text(metrics.get("accounting_equity", 0)), "Net ownership position", "teal"),
    ], columns=3, styles=styles))
    assets = float(metrics.get("accounting_assets", 0) or 0)
    liabilities = float(metrics.get("accounting_liabilities", 0) or 0)
    equity = float(metrics.get("accounting_equity", 0) or 0)
    equation_gap = assets - liabilities - equity
    story.append(callout(
        "Accounting equation",
        f"Assets {money_text(assets)} - liabilities {money_text(liabilities)} - equity {money_text(equity)} = {money_text(equation_gap)}. "
        + ("The statement balances within rounding tolerance." if abs(equation_gap) <= 0.05 else "The difference is an exception that should be investigated."),
        tone="green" if abs(equation_gap) <= 0.05 else "red",
        styles=styles,
    ))

    story.extend(section("Money movement and treasury", "This section explains how operational cash and electronic money moved during the reporting period.", styles=styles))
    story.append(metric_grid([
        ("Opening sources", money_text(metrics.get("treasury_opening_sources", 0)), "Confirmed opening funds", "slate"),
        ("Money in", money_text(metrics.get("treasury_money_in", 0)), "Collections and other inflows", "green"),
        ("Money out", money_text(metrics.get("treasury_money_out", 0)), "Disbursements and expenses", "red"),
        ("Loan collections", money_text(metrics.get("treasury_loan_collections", 0)), "Borrower repayments received", "teal"),
        ("Loan disbursements", money_text(metrics.get("treasury_loan_disbursements", 0)), "Capital issued to borrowers", "blue"),
        ("Operating expenses", money_text(metrics.get("treasury_operating_expenses", 0)), "Treasury-classified costs", "amber"),
    ], columns=2, styles=styles))

    channel_prefixes: set[str] = set()
    for key in metrics:
        if not key.startswith("channel_"):
            continue
        for suffix in ("_money_in", "_money_out", "_net"):
            if key.endswith(suffix):
                channel_prefixes.add(key[:-len(suffix)])
                break
    channel_keys = sorted(channel_prefixes)
    if channel_keys:
        story.extend(section("Payment-channel analysis", "Each channel is presented as a short movement narrative rather than a dense transaction table.", styles=styles))
        for index, prefix in enumerate(channel_keys, start=1):
            name = prefix.replace("channel_", "").replace("_", " ").title()
            money_in = metrics.get(f"{prefix}_money_in", 0)
            money_out = metrics.get(f"{prefix}_money_out", 0)
            net = metrics.get(f"{prefix}_net", 0)
            tone = "green" if float(net or 0) >= 0 else "amber"
            story.append(timeline_card(
                str(index),
                name,
                f"The channel received <b>{money_text(money_in)}</b> and paid out <b>{money_text(money_out)}</b>. Its net movement for the period is <b>{money_text(net)}</b>.",
                status="positive" if float(net or 0) >= 0 else "negative",
                tone=tone,
                styles=styles,
            ))
            story.append(Spacer(1, 2 * mm))

    story.extend(section("Loan portfolio quality", "Portfolio size is considered together with arrears, repayments and completed accounts.", styles=styles))
    story.append(metric_grid([
        ("Principal portfolio", money_text(metrics.get("principal_portfolio", 0)), "Total original principal", "blue"),
        ("Outstanding balance", money_text(metrics.get("outstanding_balance", 0)), "Unpaid borrower balances", "amber"),
        ("Amount paid", money_text(metrics.get("amount_paid", 0)), "Cumulative recorded repayments", "green"),
        ("Active loans", _report_value("active_loans", metrics.get("active_loans", 0)), "Approved or active accounts", "teal"),
        ("Completed loans", _report_value("completed_loans", metrics.get("completed_loans", 0)), "Fully completed accounts", "green"),
        ("Overdue loans", _report_value("overdue_loans", metrics.get("overdue_loans", 0)), "Accounts requiring attention", "red" if float(metrics.get("overdue_loans", 0) or 0) > 0 else "slate"),
    ], columns=2, styles=styles))
    story.append(progress_bar(
        "Portfolio overdue rate",
        float(metrics.get("portfolio_overdue_rate", 0) or 0),
        note="Lower is better",
        tone="red" if float(metrics.get("portfolio_overdue_rate", 0) or 0) >= 20 else "amber" if float(metrics.get("portfolio_overdue_rate", 0) or 0) > 0 else "green",
        styles=styles,
    ))

    story.extend(section("Operations and controls", "Volume indicators are paired with audit and branch-reconciliation exceptions.", styles=styles))
    operations_left = detail_card(
        "Lending activity",
        [
            ("Requests engaged", _report_value("loan_requests_engaged", metrics.get("loan_requests_engaged", 0))),
            ("Offers created", _report_value("offers_created", metrics.get("offers_created", 0))),
            ("Offers accepted", _report_value("offers_accepted", metrics.get("offers_accepted", 0))),
            ("Request-to-offer rate", _report_value("request_to_offer_rate", metrics.get("request_to_offer_rate", 0))),
            ("Successful transactions", _report_value("successful_transactions", metrics.get("successful_transactions", 0))),
        ],
        tone="blue",
    )
    controls_right = detail_card(
        "Control indicators",
        [
            ("Audit events", _report_value("audit_events", metrics.get("audit_events", 0))),
            ("Failed audit events", _report_value("failed_audit_events", metrics.get("failed_audit_events", 0))),
            ("Critical audit events", _report_value("critical_audit_events", metrics.get("critical_audit_events", 0))),
            ("Submission days", _report_value("branch_submission_days", metrics.get("branch_submission_days", 0))),
            ("Absolute variance", money_text(metrics.get("absolute_branch_variance", 0))),
        ],
        tone="red" if float(metrics.get("critical_audit_events", 0) or 0) > 0 or float(metrics.get("absolute_branch_variance", 0) or 0) > 0 else "green",
    )
    story.append(two_card_row(operations_left, controls_right))

    story.extend(section("Management interpretation", "These statements are generated from the report metrics and identify the issues that deserve immediate review.", styles=styles))
    for heading, narrative, tone in _accounting_insights(metrics):
        story.append(callout(heading, narrative, tone=tone, styles=styles))
        story.append(Spacer(1, 2 * mm))

    recognised = {
        "accounting_revenue", "accounting_expenses", "accounting_net_profit", "accounting_assets",
        "accounting_liabilities", "accounting_equity", "treasury_opening_sources",
        "treasury_owner_contributions", "treasury_money_in", "treasury_money_out",
        "treasury_net_movement", "treasury_operating_expenses", "treasury_loan_collections",
        "treasury_loan_disbursements", "principal_portfolio", "outstanding_balance", "amount_paid",
        "active_loans", "completed_loans", "overdue_loans", "portfolio_overdue_rate",
        "loan_requests_engaged", "offers_created", "offers_accepted", "request_to_offer_rate",
        "successful_transactions", "successful_payment_value", "failed_transactions", "audit_events",
        "failed_audit_events", "critical_audit_events", "branch_submission_days",
        "automatic_branch_submissions", "branch_submissions_with_variance", "absolute_branch_variance",
    }
    additional = [(key, value) for key, value in metrics.items() if key not in recognised and not key.startswith("channel_")]
    if additional:
        story.extend(section("Additional indicators", "Supporting indicators are grouped into readable cards rather than one long metrics table.", styles=styles))
        midpoint = (len(additional) + 1) // 2
        left_pairs = [(key.replace("_", " ").title(), _report_value(key, value)) for key, value in additional[:midpoint]]
        right_pairs = [(key.replace("_", " ").title(), _report_value(key, value)) for key, value in additional[midpoint:]]
        left_card = detail_card("Operational indicators", left_pairs or [("No additional indicators", "-")], tone="slate")
        right_card = detail_card("People and performance", right_pairs or [("No additional indicators", "-")], tone="teal")
        story.append(two_card_row(left_card, right_card))

    story.append(Spacer(1, 4 * mm))
    story.append(callout(
        "Report use",
        "This report is generated from posted and approved LoanHub records. It should be reviewed together with source documents, individual payment slips, journal entries, branch submissions and signed credit agreements before management or regulatory decisions are made.",
        tone="blue",
        styles=styles,
    ))

    context = DocumentContext(
        db=db,
        company=company,
        title="Management and Accounting Report",
        reference=reference,
        footer_note=generated_timestamp(),
        confidential=True,
    )
    return build_document(
        story=story,
        context=context,
        title=title,
        author=f"{safe_text(getattr(company, 'name', None), 'LoanHub')} via {settings.PRODUCT_NAME}",
        subject="Management, accounting, treasury and portfolio report",
    )

def build_csv(metrics: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["LoanHub Report", metadata["title"]])
    writer.writerow(["Developed by", "Ithute Solutions"])
    writer.writerow(["Reference", metadata["reference"]])
    writer.writerow(["Scope", metadata["scope_name"]])
    writer.writerow(["Period start", metadata["period_start"]])
    writer.writerow(["Period end", metadata["period_end"]])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    for key, value in metrics.items():
        writer.writerow([key.replace("_", " ").title(), value])
    return output.getvalue().encode("utf-8-sig")


def generate_report(
    db: Session,
    *,
    report_type: str,
    output_format: str,
    scope_type: str,
    period_start: date,
    period_end: date,
    company_id=None,
    branch_id=None,
    generated_by_user_id=None,
    schedule_id=None,
) -> GeneratedReport:
    reference = report_reference()
    scope_name = _scope_name(db, company_id, branch_id)
    title = f"{report_type.title()} Report - {scope_name}"
    metrics = collect_metrics(
        db,
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
    )
    metadata = {
        "title": title,
        "reference": reference,
        "scope_name": scope_name,
        "period_start": period_start,
        "period_end": period_end,
    }
    if output_format == "csv":
        content = build_csv(metrics, metadata)
        mime_type = "text/csv"
        extension = "csv"
    else:
        company = db.get(LoanCompany, company_id) if company_id else None
        content = build_pdf(
            db=db,
            company=company,
            title=title,
            reference=reference,
            scope_name=scope_name,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            report_type=report_type,
        )
        mime_type = "application/pdf"
        extension = "pdf"

    file = store_bytes(
        db,
        content=content,
        original_name=f"{reference}-{report_type}.{extension}",
        mime_type=mime_type,
        owner_user_id=generated_by_user_id,
        company_id=company_id,
        branch_id=branch_id,
        category="reports",
        visibility="company" if company_id else "platform",
        description=title,
        linked_entity_type="generated_report",
        linked_entity_id=reference,
    )
    report = GeneratedReport(
        reference=reference,
        scope_type=scope_type,
        company_id=company_id,
        branch_id=branch_id,
        schedule_id=schedule_id,
        generated_by_user_id=generated_by_user_id,
        file_id=file.id,
        title=title,
        report_type=report_type,
        output_format=output_format,
        period_start=period_start,
        period_end=period_end,
        status="completed",
        metrics=metrics,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.flush()
    return report


def run_due_report_schedules(db: Session) -> int:
    now = datetime.now(timezone.utc)
    schedules = (
        db.query(ReportSchedule)
        .filter(
            ReportSchedule.is_active.is_(True),
            ReportSchedule.next_run_at <= now,
        )
        .with_for_update(skip_locked=True)
        .all()
    )
    completed = 0
    for schedule in schedules:
        try:
            start, end = period_for_frequency(schedule.frequency, now.date())
            generate_report(
                db,
                report_type=schedule.report_type,
                output_format=schedule.output_format,
                scope_type=schedule.scope_type,
                period_start=start,
                period_end=end,
                company_id=schedule.company_id,
                branch_id=schedule.branch_id,
                generated_by_user_id=schedule.created_by_user_id,
                schedule_id=schedule.id,
            )
            schedule.last_run_at = now
            schedule.last_status = "completed"
            schedule.last_error = None
            completed += 1
        except Exception as error:
            schedule.last_run_at = now
            schedule.last_status = "failed"
            schedule.last_error = str(error)[:2000]
        schedule.next_run_at = next_run_for_frequency(schedule.frequency, now + timedelta(minutes=1))
    return completed
