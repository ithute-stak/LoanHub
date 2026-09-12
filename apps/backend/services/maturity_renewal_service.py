from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import InstallmentStatus, LoanStatus, NotificationType
from database.models.lending_operations import CollectionCase
from database.models.maturity_recovery import LoanRenewalCycle, MaturityRenewalPolicy
from database.models.notification import Notification
from database.models.repayment import RepaymentInstallment
from services.interest_calculation_service import calculate_loan_terms, generate_monthly_due_dates

MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def local_today() -> date:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE)).date()


def get_or_create_maturity_policy(db: Session, company_id: UUID) -> MaturityRenewalPolicy:
    row = db.query(MaturityRenewalPolicy).filter(MaturityRenewalPolicy.company_id == company_id).first()
    if row:
        return row
    row = MaturityRenewalPolicy(company_id=company_id, enabled=False)
    db.add(row)
    db.flush()
    return row


def effective_auto_renewal(loan: ClientCompanyLoan, policy: MaturityRenewalPolicy) -> bool:
    if loan.renewal_stopped_at is not None:
        return False
    return bool(policy.enabled if loan.automatic_renewal_enabled is None else loan.automatic_renewal_enabled)


def _matured(loan: ClientCompanyLoan, policy: MaturityRenewalPolicy, today: date) -> bool:
    return bool(
        loan.maturity_date
        and money(loan.balance) > 0
        and loan.maturity_date + timedelta(days=max(0, int(policy.grace_days or 0))) < today
    )


def _collection_ref() -> str:
    return f"COL-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def ensure_collection_case_for_loan(
    db: Session,
    loan: ClientCompanyLoan,
    *,
    today: date | None = None,
    next_action_at: datetime | None = None,
) -> CollectionCase:
    today = today or local_today()
    case = db.query(CollectionCase).filter(
        CollectionCase.company_id == loan.company_id,
        CollectionCase.loan_id == loan.id,
    ).first()
    days = max((today - (loan.maturity_date or today)).days, 0)
    stage = "early_arrears" if days <= 30 else "late_arrears" if days <= 90 else "pre_legal"
    priority = "normal" if days <= 30 else "high" if days <= 90 else "urgent"
    if not case:
        case = CollectionCase(
            company_id=loan.company_id,
            branch_id=loan.branch_id,
            borrower_id=loan.borrower_id,
            loan_id=loan.id,
            case_reference=_collection_ref(),
            status="open",
            stage=stage,
            days_past_due=days,
            overdue_amount=money(loan.balance),
            outstanding_balance=money(loan.balance),
            priority=priority,
            next_action_at=next_action_at,
            notes="Automatic maturity renewal is disabled or stopped; recovery follow-up is required.",
        )
        db.add(case)
        db.flush()
    else:
        if case.status in {"recovered", "closed"}:
            case.status = "open"
        if case.stage != "legal":
            case.stage = stage
        case.days_past_due = days
        case.overdue_amount = money(loan.balance)
        case.outstanding_balance = money(loan.balance)
        case.priority = priority
        if next_action_at and not case.next_action_at:
            case.next_action_at = next_action_at
    return case


def _snapshot(row: RepaymentInstallment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "installment_number": row.installment_number,
        "due_date": row.due_date.isoformat(),
        "principal_due": str(money(row.principal_due)),
        "interest_due": str(money(row.interest_due)),
        "fee_due": str(money(row.fee_due)),
        "total_due": str(money(row.total_due)),
        "paid_amount": str(money(row.paid_amount)),
        "status": getattr(row.status, "value", row.status),
        "renewal_cycle_id": str(row.renewal_cycle_id) if row.renewal_cycle_id else None,
        "is_superseded": bool(row.is_superseded),
    }


def _original_terms(db: Session, loan: ClientCompanyLoan) -> dict[str, Any]:
    first = db.query(LoanRenewalCycle).filter(
        LoanRenewalCycle.loan_id == loan.id,
        LoanRenewalCycle.cycle_number == 1,
    ).first()
    if first and first.previous_terms_snapshot:
        return dict(first.previous_terms_snapshot)
    return {
        "interest_rate": str(loan.interest_rate or 0),
        "processing_fee": str(loan.processing_fee or 0),
        "repayment_period": int(loan.repayment_period or 0),
    }


def _notify_borrower(db: Session, loan: ClientCompanyLoan, cycle: LoanRenewalCycle) -> None:
    borrower = getattr(loan, "borrower", None)
    user_id = getattr(borrower, "user_id", None) if borrower else None
    if not user_id:
        return
    key = f"maturity-renewal:borrower:{loan.id}:{cycle.cycle_number}"
    if db.query(Notification.id).filter(Notification.deduplication_key == key).first():
        return
    db.add(Notification(
        user_id=user_id,
        company_id=loan.company_id,
        branch_id=loan.branch_id,
        title="Loan balance renewed",
        message=(
            f"{loan.loan_reference} reached maturity with LSL {money(cycle.opening_balance):.2f} remaining. "
            f"Renewal cycle {cycle.cycle_number} now matures on {cycle.maturity_date.isoformat()}."
        ),
        notification_type=NotificationType.SYSTEM,
        event_type="loan.maturity_renewed",
        action="view",
        entity_type="loan",
        entity_id=str(loan.id),
        action_url="/borrower/loans",
        icon="calendar-clock",
        priority="high",
        data={
            "cycle_number": cycle.cycle_number,
            "opening_balance": str(money(cycle.opening_balance)),
            "new_total_repayable": str(money(cycle.total_repayable)),
            "new_installment": str(money(cycle.installment_amount)),
            "maturity_date": cycle.maturity_date.isoformat(),
        },
        deduplication_key=key,
    ))


def renew_matured_loan(
    db: Session,
    loan: ClientCompanyLoan,
    policy: MaturityRenewalPolicy,
    *,
    automatic: bool = True,
    actor_user_id: UUID | None = None,
    today: date | None = None,
) -> LoanRenewalCycle | None:
    today = today or local_today()
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED} or not _matured(loan, policy, today):
        return None
    if not effective_auto_renewal(loan, policy):
        ensure_collection_case_for_loan(db, loan, today=today, next_action_at=datetime.combine(today, time(hour=7)))
        return None
    if policy.max_cycles is not None and int(loan.renewal_cycle_count or 0) >= int(policy.max_cycles):
        loan.automatic_renewal_enabled = False
        loan.renewal_stopped_at = datetime.now(timezone.utc)
        loan.renewal_stop_reason = f"Configured maximum of {policy.max_cycles} renewal cycle(s) reached"
        ensure_collection_case_for_loan(db, loan, today=today, next_action_at=datetime.combine(today, time(hour=7)))
        return None

    loan = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == loan.id).with_for_update().one()
    cycle_number = int(loan.renewal_cycle_count or 0) + 1
    existing = db.query(LoanRenewalCycle).filter(
        LoanRenewalCycle.loan_id == loan.id,
        LoanRenewalCycle.cycle_number == cycle_number,
    ).first()
    if existing:
        return existing

    opening_balance = money(loan.balance)
    original = _original_terms(db, loan)
    rate = Decimal(str(original.get("interest_rate") or 0)) if policy.reuse_original_rate else Decimal(str(policy.renewal_rate_percent or 0))
    term = int(original.get("repayment_period") or 0) if policy.reuse_original_term else int(policy.renewal_term_months or 0)
    if not 1 <= term <= 120:
        raise ValueError("Renewal term must be between 1 and 120 months")
    fee = money(original.get("processing_fee") or 0) if policy.include_processing_fee else money(0)
    method = str(loan.calculation_method or "micro_loan")
    old_maturity = loan.maturity_date
    start_date = old_maturity + timedelta(days=1)
    due_dates = generate_monthly_due_dates(start_date, term)
    installment, renewed_total, details = calculate_loan_terms(
        principal=opening_balance,
        rate_percent=rate,
        term_months=term,
        processing_fee=fee,
        interest_method=method,
        start_date=start_date,
        due_dates=due_dates,
    )

    schedule = db.query(RepaymentInstallment).filter(
        RepaymentInstallment.loan_id == loan.id,
        RepaymentInstallment.is_superseded.is_(False),
    ).order_by(RepaymentInstallment.installment_number.asc()).all()
    previous_terms = {
        "principal_amount": str(money(loan.principal_amount)),
        "interest_rate": str(loan.interest_rate or 0),
        "processing_fee": str(money(loan.processing_fee)),
        "total_repayable": str(money(loan.total_repayable)),
        "amount_paid": str(money(loan.amount_paid)),
        "balance": str(opening_balance),
        "repayment_period": loan.repayment_period,
        "installment_amount": str(money(loan.installment_amount)),
        "calculation_method": method,
        "first_payment_due": loan.first_payment_due.isoformat() if loan.first_payment_due else None,
        "maturity_date": old_maturity.isoformat(),
        "calculation_breakdown": dict(loan.calculation_breakdown or {}),
    }
    db.query(LoanRenewalCycle).filter(
        LoanRenewalCycle.loan_id == loan.id,
        LoanRenewalCycle.status == "active",
    ).update({LoanRenewalCycle.status: "completed"}, synchronize_session=False)

    now = datetime.now(timezone.utc)
    cycle = LoanRenewalCycle(
        company_id=loan.company_id,
        loan_id=loan.id,
        borrower_id=loan.borrower_id,
        cycle_number=cycle_number,
        status="active",
        automatic=automatic,
        opening_balance=opening_balance,
        rollover_basis=policy.rollover_basis,
        rate_percent=rate,
        processing_fee=fee,
        term_months=term,
        calculation_method=method,
        installment_amount=installment,
        total_repayable=renewed_total,
        started_on=start_date,
        maturity_date=due_dates[-1],
        rolled_at=now,
        previous_terms_snapshot=previous_terms,
        previous_schedule_snapshot=[_snapshot(row) for row in schedule],
        calculation_breakdown=details,
        created_by_user_id=actor_user_id,
    )
    db.add(cycle)
    db.flush()

    for row in schedule:
        if row.status not in {InstallmentStatus.PAID, InstallmentStatus.WAIVED} and money(row.paid_amount) < money(row.total_due):
            row.is_superseded = True
            row.superseded_at = now
            row.superseded_by_cycle_id = cycle.id

    max_number = db.query(func.coalesce(func.max(RepaymentInstallment.installment_number), 0)).filter(
        RepaymentInstallment.loan_id == loan.id,
    ).scalar() or 0
    for offset, raw in enumerate(details.get("schedule_rows") or [], start=1):
        db.add(RepaymentInstallment(
            loan_id=loan.id,
            renewal_cycle_id=cycle.id,
            installment_number=int(max_number) + offset,
            due_date=date.fromisoformat(str(raw["due_date"])),
            principal_due=money(raw["principal_due"]),
            interest_due=money(raw["interest_due"]),
            fee_due=money(raw.get("fee_due", 0)),
            total_due=money(raw["total_due"]),
            paid_amount=money(0),
            status=InstallmentStatus.PENDING,
            is_superseded=False,
        ))

    if loan.original_maturity_date is None:
        loan.original_maturity_date = old_maturity
    loan.renewal_cycle_count = cycle_number
    loan.last_renewed_at = now
    loan.first_payment_due = due_dates[0]
    loan.maturity_date = due_dates[-1]
    loan.interest_rate = rate
    loan.repayment_period = term
    loan.installment_amount = installment
    loan.total_repayable = money(loan.amount_paid) + money(renewed_total)
    loan.balance = money(renewed_total)
    loan.calculation_breakdown = details
    loan.status = LoanStatus.ACTIVE
    loan.is_overdue = False

    case = db.query(CollectionCase).filter(CollectionCase.company_id == loan.company_id, CollectionCase.loan_id == loan.id).first()
    if case and case.stage != "legal" and case.status not in {"written_off", "closed"}:
        case.status, case.stage, case.priority = "recovered", "renewal", "normal"
        case.overdue_amount, case.days_past_due, case.next_action_at = money(0), 0, None
        case.outstanding_balance = money(loan.balance)

    if policy.notify_borrower:
        _notify_borrower(db, loan, cycle)
    return cycle


def process_maturity_renewals(
    db: Session,
    *,
    today: date | None = None,
    company_id: UUID | None = None,
) -> dict[str, int]:
    today = today or local_today()
    query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        ClientCompanyLoan.balance > 0,
        ClientCompanyLoan.maturity_date.is_not(None),
        ClientCompanyLoan.maturity_date < today,
    )
    if company_id:
        query = query.filter(ClientCompanyLoan.company_id == company_id)
    renewed = collections_started = skipped = 0
    policies: dict[UUID, MaturityRenewalPolicy] = {}
    for loan in query.order_by(ClientCompanyLoan.maturity_date.asc()).all():
        policy = policies.get(loan.company_id)
        if policy is None:
            policy = get_or_create_maturity_policy(db, loan.company_id)
            policies[loan.company_id] = policy
        had_case = bool(db.query(CollectionCase.id).filter(CollectionCase.company_id == loan.company_id, CollectionCase.loan_id == loan.id).first())
        cycle = renew_matured_loan(db, loan, policy, today=today)
        if cycle:
            renewed += 1
        elif not effective_auto_renewal(loan, policy):
            has_case = bool(db.query(CollectionCase.id).filter(CollectionCase.company_id == loan.company_id, CollectionCase.loan_id == loan.id).first())
            collections_started += int(has_case and not had_case)
            skipped += int(had_case)
        else:
            skipped += 1
    return {"renewed": renewed, "collections_started": collections_started, "skipped": skipped}
