from __future__ import annotations

import csv
import io
import secrets
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database.models.branch import CompanyBranch
from database.models.enums import (
    BranchTransferStatus,
    OpeningSourceType,
    PaymentDirection,
    PaymentMethod,
    PaymentPurpose,
    TreasuryDayStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.models.payment import PaymentTransaction
from database.models.treasury import (
    BranchDailyLedger,
    BranchDailySubmission,
    BranchFundingTransfer,
    BranchOpeningSource,
    ExpenseCategory,
    TreasuryEntry,
    TreasurySettings,
)
from database.schemas.treasury import OpeningSourceCreate, TreasuryEntryCreate


MONEY = Decimal("0.01")
PAYMENT_METHOD_LABELS: dict[PaymentMethod, str] = {
    PaymentMethod.LELEFAPAYGATE: "LelefaPayGate",
    PaymentMethod.BANK: "Bank",
    PaymentMethod.SWIPPED: "Swipped",
    PaymentMethod.GOLINK: "goLink",
    PaymentMethod.CDAS: "CDAS",
    PaymentMethod.MPESA_WALLET: "M-Pesa Wallet",
    PaymentMethod.MPESA_MERCHANT: "M-Pesa Merchant",
    PaymentMethod.MPESA_AGENT: "M-Pesa Agent",
    PaymentMethod.ECOCASH_WALLET: "EcoCash Wallet",
    PaymentMethod.ECOCASH_AGENT: "EcoCash Agent",
    PaymentMethod.ECOCASH_MERCHANT: "EcoCash Merchant",
    PaymentMethod.CASH: "Cash",
}


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def resolve_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(status_code=422, detail="The configured treasury timezone is invalid") from error


def local_business_date(settings: TreasurySettings, value: datetime | None = None) -> date:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(resolve_timezone(settings.timezone)).date()


def payment_method_options() -> list[dict[str, object]]:
    """Expose the active posting boundary, not historical channel values."""
    return [
        {
            "value": method,
            "label": PAYMENT_METHOD_LABELS[method],
            "proof_recommended": False,
        }
        for method in (PaymentMethod.LELEFAPAYGATE, PaymentMethod.CASH)
    ]


def get_or_create_settings(db: Session, company_id: UUID) -> TreasurySettings:
    row = db.query(TreasurySettings).filter(TreasurySettings.company_id == company_id).first()
    if row:
        return row

    headquarters = (
        db.query(CompanyBranch)
        .filter(CompanyBranch.company_id == company_id, CompanyBranch.is_active.is_(True))
        .order_by(CompanyBranch.is_headquarters.desc(), CompanyBranch.created_at.asc())
        .first()
    )
    row = TreasurySettings(
        company_id=company_id,
        headquarters_branch_id=headquarters.id if headquarters else None,
        currency="LSL",
        timezone="Africa/Maseru",
        auto_open_enabled=True,
        auto_open_time=time(0, 1),
        auto_submit_enabled=True,
        auto_submit_time=time(16, 30),
        require_proof_for_non_cash=True,
        allow_branch_reopen=False,
        expense_approval_threshold=0,
        dual_control_expenses=True,
    )
    if headquarters:
        headquarters.is_headquarters = True
    db.add(row)
    db.flush()
    return row


def set_headquarters_branch(db: Session, settings: TreasurySettings, branch_id: UUID | None) -> None:
    branches = db.query(CompanyBranch).filter(CompanyBranch.company_id == settings.company_id).all()
    selected = None
    for branch in branches:
        branch.is_headquarters = branch.id == branch_id
        if branch.is_headquarters:
            selected = branch
    if branch_id and not selected:
        raise HTTPException(status_code=404, detail="Headquarters branch was not found in this company")
    settings.headquarters_branch_id = branch_id


def headquarters_branch(db: Session, company_id: UUID) -> CompanyBranch | None:
    settings = get_or_create_settings(db, company_id)
    if settings.headquarters_branch_id:
        branch = db.get(CompanyBranch, settings.headquarters_branch_id)
        if branch and branch.company_id == company_id:
            return branch
    return (
        db.query(CompanyBranch)
        .filter(CompanyBranch.company_id == company_id, CompanyBranch.is_active.is_(True))
        .order_by(CompanyBranch.is_headquarters.desc(), CompanyBranch.created_at.asc())
        .first()
    )


def previous_branch_closing(db: Session, company_id: UUID, branch_id: UUID, business_date: date) -> Decimal:
    previous = (
        db.query(BranchDailyLedger)
        .filter(
            BranchDailyLedger.company_id == company_id,
            BranchDailyLedger.branch_id == branch_id,
            BranchDailyLedger.business_date < business_date,
        )
        .order_by(BranchDailyLedger.business_date.desc())
        .first()
    )
    if not previous:
        return Decimal("0.00")
    return money(previous.declared_closing_balance if previous.declared_closing_balance is not None else previous.expected_closing_balance)


def _previous_source_reference(branch_id: UUID, business_date: date, payment_method: PaymentMethod | None = None) -> str:
    base = f"PREVIOUS-CLOSING:{branch_id}:{business_date.isoformat()}"
    return f"{base}:{payment_method.value}" if payment_method else base


def previous_branch_channel_closing(
    db: Session,
    company_id: UUID,
    branch_id: UUID,
    business_date: date,
) -> dict[PaymentMethod, Decimal]:
    """Carry the prior branch close forward by payment channel.

    Earlier releases carried the whole previous closing as ``cash``. That made
    the next day's channel position inaccurate whenever bank/mobile-money
    balances existed. We now reconstruct each channel from the previous day's
    confirmed opening sources and posted movements. Any declared closing
    variance that cannot be attributed to a channel is carried on Cash as the
    explicit balancing channel so the channel total still equals the branch
    closing balance.
    """
    previous = (
        db.query(BranchDailyLedger)
        .filter(
            BranchDailyLedger.company_id == company_id,
            BranchDailyLedger.branch_id == branch_id,
            BranchDailyLedger.business_date < business_date,
        )
        .order_by(BranchDailyLedger.business_date.desc())
        .first()
    )
    positions = {method: Decimal("0.00") for method in PaymentMethod}
    if not previous:
        return positions

    sources = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.daily_ledger_id == previous.id,
        BranchOpeningSource.is_voided.is_(False),
        BranchOpeningSource.is_confirmed.is_(True),
    ).all()
    for source in sources:
        positions[source.payment_method] = money(positions[source.payment_method] + money(source.amount))

    entries = db.query(TreasuryEntry).filter(
        TreasuryEntry.daily_ledger_id == previous.id,
        TreasuryEntry.is_voided.is_(False),
        _posted_entry_filter(),
    ).all()
    for entry in entries:
        amount = money(entry.amount)
        if entry.direction == TreasuryDirection.MONEY_IN:
            positions[entry.payment_method] = money(positions[entry.payment_method] + amount)
        else:
            positions[entry.payment_method] = money(positions[entry.payment_method] - amount)

    expected_total = money(sum(positions.values(), Decimal("0.00")))
    confirmed_total = money(
        previous.declared_closing_balance
        if previous.declared_closing_balance is not None
        else previous.expected_closing_balance
    )
    difference = money(confirmed_total - expected_total)
    if difference:
        positions[PaymentMethod.CASH] = money(positions[PaymentMethod.CASH] + difference)
    return positions


def _ensure_previous_closing_source(db: Session, ledger: BranchDailyLedger) -> list[BranchOpeningSource]:
    positions = previous_branch_channel_closing(db, ledger.company_id, ledger.branch_id, ledger.business_date)
    existing = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.daily_ledger_id == ledger.id,
        BranchOpeningSource.source_type == OpeningSourceType.PREVIOUS_CLOSING,
    ).all()
    by_reference = {source.source_reference: source for source in existing}
    legacy_reference = _previous_source_reference(ledger.branch_id, ledger.business_date)
    touched: set[UUID] = set()
    rows: list[BranchOpeningSource] = []

    for method in PaymentMethod:
        amount = money(positions[method])
        reference = _previous_source_reference(ledger.branch_id, ledger.business_date, method)
        source = by_reference.get(reference)
        if source is None and method == PaymentMethod.CASH:
            source = by_reference.get(legacy_reference)
            if source is not None:
                source.source_reference = reference
        if source is None:
            if amount == 0:
                continue
            source = BranchOpeningSource(
                company_id=ledger.company_id,
                branch_id=ledger.branch_id,
                daily_ledger_id=ledger.id,
                source_type=OpeningSourceType.PREVIOUS_CLOSING,
                payment_method=method,
                amount=amount,
                currency="LSL",
                description=f"Previous business day's confirmed {PAYMENT_METHOD_LABELS[method]} closing balance",
                source_reference=reference,
                is_system_generated=True,
                is_confirmed=True,
                confirmed_at=datetime.now(timezone.utc),
            )
            db.add(source)
            db.flush()
        else:
            source.payment_method = method
            source.amount = amount
            source.currency = "LSL"
            source.description = f"Previous business day's confirmed {PAYMENT_METHOD_LABELS[method]} closing balance"
            source.is_system_generated = True
            source.is_confirmed = True
            if source.confirmed_at is None:
                source.confirmed_at = datetime.now(timezone.utc)
        touched.add(source.id)
        rows.append(source)

    # Legacy channel rows that are no longer required stay in the audit trail
    # but carry zero, preventing historical double counting.
    for source in existing:
        if source.id not in touched:
            source.amount = Decimal("0.00")
    return rows


def get_or_create_daily_ledger(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID,
    business_date: date,
) -> BranchDailyLedger:
    ledger = (
        db.query(BranchDailyLedger)
        .filter(
            BranchDailyLedger.company_id == company_id,
            BranchDailyLedger.branch_id == branch_id,
            BranchDailyLedger.business_date == business_date,
        )
        .first()
    )
    if ledger:
        # A submitted day is a frozen operational snapshot. Read paths must not
        # silently rewrite its carried-forward opening composition. Reopened
        # days can refresh because they are explicitly writable again.
        if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
            _ensure_previous_closing_source(db, ledger)
        return ledger
    branch = db.get(CompanyBranch, branch_id)
    if not branch or branch.company_id != company_id:
        raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    ledger = BranchDailyLedger(
        company_id=company_id,
        branch_id=branch_id,
        business_date=business_date,
        status=TreasuryDayStatus.OPEN,
        opening_balance=0,
        total_money_in=0,
        total_money_out=0,
        expected_closing_balance=0,
        variance_amount=0,
        entry_count=0,
        pending_entry_count=0,
    )
    db.add(ledger)
    db.flush()
    _ensure_previous_closing_source(db, ledger)
    recalculate_daily_ledger(db, ledger)
    return ledger


def assert_ledger_writable(ledger: BranchDailyLedger) -> None:
    if ledger.status not in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The {ledger.business_date.isoformat()} branch day is locked after submission. "
                "An authorised manager must reopen that date; the next business day opens automatically at 00:01."
            ),
        )


def ensure_current_payment_day_writable(
    db: Session,
    ledger: BranchDailyLedger,
    *,
    settings: TreasurySettings,
    occurred_at: datetime,
) -> BranchDailyLedger:
    """Keep the live business day writable for new payment transactions.

    Older LoanHub deployments automatically submitted the current branch day at
    the configured afternoon cut-off (16:30 by default). That made a perfectly
    valid repayment preview succeed but the real posting fail later when the
    treasury entry was created.

    A current-day ledger is reopened automatically only when its latest
    submission was created by the automatic scheduler. A day that a person
    deliberately submitted remains locked and still requires an authorised
    manual reopen. This preserves the audit trail while preventing the scheduler
    from blocking normal evening payments.
    """
    if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        return ledger

    if ledger.business_date != local_business_date(settings, occurred_at):
        assert_ledger_writable(ledger)
        return ledger

    latest_submission = (
        db.query(BranchDailySubmission)
        .filter(BranchDailySubmission.daily_ledger_id == ledger.id)
        .order_by(
            BranchDailySubmission.sequence_number.desc(),
            BranchDailySubmission.submitted_at.desc(),
        )
        .first()
    )

    if not latest_submission or not latest_submission.is_automatic:
        assert_ledger_writable(ledger)
        return ledger

    return reopen_daily_ledger(
        db,
        ledger,
        reason=(
            "Automatically reopened because a live payment was received on the "
            "same business date after an automatic treasury submission."
        ),
    )


def _posted_entry_filter():
    return TreasuryEntry.approval_status.in_([
        TreasuryEntryApprovalStatus.POSTED,
        TreasuryEntryApprovalStatus.APPROVED,
    ])


def recalculate_daily_ledger(db: Session, ledger: BranchDailyLedger) -> BranchDailyLedger:
    opening = (
        db.query(func.coalesce(func.sum(BranchOpeningSource.amount), 0))
        .filter(
            BranchOpeningSource.daily_ledger_id == ledger.id,
            BranchOpeningSource.is_voided.is_(False),
            BranchOpeningSource.is_confirmed.is_(True),
        )
        .scalar()
    )
    totals = (
        db.query(
            TreasuryEntry.direction,
            func.coalesce(func.sum(TreasuryEntry.amount), 0),
            func.count(TreasuryEntry.id),
        )
        .filter(
            TreasuryEntry.daily_ledger_id == ledger.id,
            TreasuryEntry.is_voided.is_(False),
            _posted_entry_filter(),
        )
        .group_by(TreasuryEntry.direction)
        .all()
    )
    pending_count = (
        db.query(func.count(TreasuryEntry.id))
        .filter(
            TreasuryEntry.daily_ledger_id == ledger.id,
            TreasuryEntry.is_voided.is_(False),
            TreasuryEntry.approval_status == TreasuryEntryApprovalStatus.PENDING,
        )
        .scalar()
        or 0
    )
    money_in = Decimal("0.00")
    money_out = Decimal("0.00")
    count = 0
    for direction, amount, row_count in totals:
        if direction == TreasuryDirection.MONEY_IN:
            money_in += money(amount)
        else:
            money_out += money(amount)
        count += int(row_count or 0)
    ledger.opening_balance = money(opening)
    ledger.total_money_in = money(money_in)
    ledger.total_money_out = money(money_out)
    ledger.expected_closing_balance = money(ledger.opening_balance + money_in - money_out)
    ledger.entry_count = count
    ledger.pending_entry_count = int(pending_count)
    if ledger.declared_closing_balance is not None:
        ledger.variance_amount = money(ledger.declared_closing_balance - ledger.expected_closing_balance)
    else:
        ledger.variance_amount = Decimal("0.00")
    db.flush()
    return ledger


def validate_manual_proof(
    settings: TreasurySettings,
    payment_method: PaymentMethod,
    proof_reference: str | None,
    proof_url: str | None,
) -> None:
    if (
        settings.require_proof_for_non_cash
        and payment_method != PaymentMethod.CASH
        and not (proof_reference and proof_reference.strip())
        and not (proof_url and proof_url.strip())
    ):
        raise HTTPException(status_code=422, detail="A proof reference or proof document is required for a non-cash payment method")


def create_opening_source(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    payload: OpeningSourceCreate,
) -> BranchOpeningSource:
    settings = get_or_create_settings(db, company_id)
    target_date = payload.business_date or local_business_date(settings)
    ledger = get_or_create_daily_ledger(db, company_id=company_id, branch_id=branch_id, business_date=target_date)
    assert_ledger_writable(ledger)
    validate_manual_proof(settings, payload.payment_method, payload.proof_reference, payload.proof_url)
    reference = (payload.source_reference or "").strip() or f"OPEN-{target_date:%Y%m%d}-{secrets.token_hex(4).upper()}"
    duplicate = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.daily_ledger_id == ledger.id,
        BranchOpeningSource.source_type == payload.source_type,
        BranchOpeningSource.source_reference == reference,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This opening-balance source has already been recorded")
    source = BranchOpeningSource(
        company_id=company_id,
        branch_id=branch_id,
        daily_ledger_id=ledger.id,
        source_type=payload.source_type,
        payment_method=payload.payment_method,
        amount=money(payload.amount),
        currency=payload.currency.upper(),
        description=payload.description.strip(),
        source_reference=reference,
        proof_reference=(payload.proof_reference or "").strip() or None,
        proof_url=(payload.proof_url or "").strip() or None,
        proof_notes=(payload.proof_notes or "").strip() or None,
        is_system_generated=False,
        is_confirmed=True,
        confirmed_at=datetime.now(timezone.utc),
        confirmed_by_user_id=user_id,
        recorded_by_user_id=user_id,
    )
    db.add(source)
    db.flush()
    from services.accounting_service import record_opening_source_accounting
    record_opening_source_accounting(db, source)
    recalculate_daily_ledger(db, ledger)
    return source


def void_opening_source(db: Session, source: BranchOpeningSource, *, user_id: UUID, reason: str) -> BranchOpeningSource:
    if source.source_type == OpeningSourceType.PREVIOUS_CLOSING or source.is_system_generated:
        raise HTTPException(status_code=409, detail="System-generated previous closing cannot be voided")
    ledger = source.daily_ledger or db.get(BranchDailyLedger, source.daily_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_ledger_writable(ledger)
    if source.is_voided:
        return source
    source.is_voided = True
    source.void_reason = reason.strip()
    source.voided_at = datetime.now(timezone.utc)
    source.voided_by_user_id = user_id
    from services.accounting_service import reverse_reference_accounting
    reverse_reference_accounting(
        db, company_id=source.company_id, branch_id=source.branch_id,
        reference_type="opening_source", reference_id=str(source.id),
        user_id=user_id, reason=reason.strip(),
    )
    recalculate_daily_ledger(db, ledger)
    return source


def _requires_expense_approval(settings: TreasurySettings, payload: TreasuryEntryCreate) -> bool:
    if payload.entry_type != TreasuryEntryType.EXPENSE or payload.direction != TreasuryDirection.MONEY_OUT:
        return False
    threshold = money(settings.expense_approval_threshold)
    return threshold > 0 and money(payload.amount) >= threshold


def create_manual_entry(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    payload: TreasuryEntryCreate,
) -> TreasuryEntry:
    settings = get_or_create_settings(db, company_id)
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)
    business_date = local_business_date(settings, occurred_at)
    ledger = get_or_create_daily_ledger(db, company_id=company_id, branch_id=branch_id, business_date=business_date)
    assert_ledger_writable(ledger)
    validate_manual_proof(settings, payload.payment_method, payload.proof_reference, payload.proof_url)

    if payload.idempotency_key:
        existing = db.query(TreasuryEntry).filter(
            TreasuryEntry.company_id == company_id,
            TreasuryEntry.idempotency_key == payload.idempotency_key,
        ).first()
        if existing:
            return existing

    if payload.expense_category_id:
        category = db.get(ExpenseCategory, payload.expense_category_id)
        if not category or category.company_id != company_id or not category.is_active:
            raise HTTPException(status_code=422, detail="Choose an active expense category from this company")

    requires_approval = _requires_expense_approval(settings, payload)
    entry = TreasuryEntry(
        company_id=company_id,
        branch_id=branch_id,
        daily_ledger_id=ledger.id,
        direction=payload.direction,
        entry_type=payload.entry_type,
        payment_method=payload.payment_method,
        approval_status=(TreasuryEntryApprovalStatus.PENDING if requires_approval else TreasuryEntryApprovalStatus.POSTED),
        requires_approval=requires_approval,
        idempotency_key=payload.idempotency_key,
        voucher_number=(payload.voucher_number or "").strip() or None,
        amount=money(payload.amount),
        currency=payload.currency.upper(),
        occurred_at=occurred_at,
        description=payload.description.strip(),
        proof_reference=(payload.proof_reference or "").strip() or None,
        proof_url=(payload.proof_url or "").strip() or None,
        proof_notes=(payload.proof_notes or "").strip() or None,
        external_reference=(payload.external_reference or "").strip() or None,
        expense_category_id=payload.expense_category_id,
        loan_id=payload.loan_id,
        borrower_id=payload.borrower_id,
        recorded_by_user_id=user_id,
    )
    db.add(entry)
    db.flush()
    if entry.approval_status == TreasuryEntryApprovalStatus.POSTED:
        from services.accounting_service import record_treasury_entry_accounting
        record_treasury_entry_accounting(db, entry)
    recalculate_daily_ledger(db, ledger)
    return entry


def approve_treasury_entry(db: Session, entry: TreasuryEntry, *, user_id: UUID, reason: str | None = None) -> TreasuryEntry:
    if entry.approval_status != TreasuryEntryApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only a pending expense can be approved")
    settings = get_or_create_settings(db, entry.company_id)
    if settings.dual_control_expenses and entry.recorded_by_user_id == user_id:
        raise HTTPException(status_code=409, detail="Dual control is enabled; the person who recorded this expense cannot approve it")
    ledger = entry.daily_ledger or db.get(BranchDailyLedger, entry.daily_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_ledger_writable(ledger)
    entry.approval_status = TreasuryEntryApprovalStatus.APPROVED
    entry.approved_at = datetime.now(timezone.utc)
    entry.approved_by_user_id = user_id
    if reason:
        entry.proof_notes = "\n".join(filter(None, [entry.proof_notes, f"Approval note: {reason.strip()}"]))
    from services.accounting_service import record_treasury_entry_accounting
    record_treasury_entry_accounting(db, entry)
    recalculate_daily_ledger(db, ledger)
    return entry


def reject_treasury_entry(db: Session, entry: TreasuryEntry, *, user_id: UUID, reason: str) -> TreasuryEntry:
    if entry.approval_status != TreasuryEntryApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only a pending expense can be rejected")
    ledger = entry.daily_ledger or db.get(BranchDailyLedger, entry.daily_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_ledger_writable(ledger)
    entry.approval_status = TreasuryEntryApprovalStatus.REJECTED
    entry.rejected_at = datetime.now(timezone.utc)
    entry.rejected_by_user_id = user_id
    entry.rejection_reason = reason.strip()
    recalculate_daily_ledger(db, ledger)
    return entry


def entry_type_for_payment(payment: PaymentTransaction) -> TreasuryEntryType:
    if payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
        return TreasuryEntryType.LOAN_DISBURSEMENT
    if payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
        return TreasuryEntryType.LOAN_COLLECTION
    if payment.purpose in {PaymentPurpose.PLATFORM_FEE, PaymentPurpose.PLATFORM_TRANSACTION_CHARGE, PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT}:
        return TreasuryEntryType.PLATFORM_CHARGE
    if payment.purpose == PaymentPurpose.REFUND:
        return TreasuryEntryType.REFUND
    return TreasuryEntryType.OTHER


def resolve_payment_branch_id(
    db: Session,
    payment: PaymentTransaction,
    branch_id: UUID | None = None,
) -> UUID | None:
    """Resolve the operational branch for a company payment.

    Payment callers should pass the branch when they know it, but older and
    platform-finance paths did not always do that. Falling back through the
    linked loan, cash record, company client account and finally Headquarters
    prevents a successful company payment from silently disappearing from the
    branch treasury merely because one caller omitted ``branch_id``.
    """
    if branch_id:
        return branch_id
    if getattr(payment, "loan", None) is not None and getattr(payment.loan, "branch_id", None):
        return payment.loan.branch_id
    if getattr(payment, "cash_transaction", None) is not None and getattr(payment.cash_transaction, "branch_id", None):
        return payment.cash_transaction.branch_id
    if getattr(payment, "company_borrower_account", None) is not None and getattr(payment.company_borrower_account, "branch_id", None):
        return payment.company_borrower_account.branch_id
    if payment.company_id:
        return get_or_create_settings(db, payment.company_id).headquarters_branch_id
    return None


def record_payment_treasury_entry(
    db: Session,
    payment: PaymentTransaction,
    *,
    branch_id: UUID | None = None,
    description: str | None = None,
) -> TreasuryEntry | None:
    if not payment.company_id:
        return None
    existing = db.query(TreasuryEntry).filter(TreasuryEntry.payment_transaction_id == payment.id).first()
    if existing:
        return existing
    resolved_branch_id = resolve_payment_branch_id(db, payment, branch_id)
    if not resolved_branch_id:
        # A company without any configured branch cannot safely allocate a
        # movement. The integrity report surfaces this condition explicitly.
        return None
    settings = get_or_create_settings(db, payment.company_id)
    occurred_at = payment.completed_at or payment.created_at or datetime.now(timezone.utc)
    ledger = get_or_create_daily_ledger(
        db,
        company_id=payment.company_id,
        branch_id=resolved_branch_id,
        business_date=local_business_date(settings, occurred_at),
    )
    owner_backdated = bool((payment.provider_payload or {}).get("backdated_by_company_owner"))
    if owner_backdated and ledger.status not in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        ledger = reopen_daily_ledger(
            db,
            ledger,
            reason=(
                "Company Owner posted a verified backdated payment. "
                f"Payment {payment.provider_reference or payment.id} was applied to this historical business date."
            ),
        )
    else:
        ledger = ensure_current_payment_day_writable(
            db,
            ledger,
            settings=settings,
            occurred_at=occurred_at,
        )
    assert_ledger_writable(ledger)
    direction = TreasuryDirection.MONEY_IN if payment.direction == PaymentDirection.INBOUND else TreasuryDirection.MONEY_OUT
    entry = TreasuryEntry(
        company_id=payment.company_id,
        branch_id=resolved_branch_id,
        daily_ledger_id=ledger.id,
        direction=direction,
        entry_type=entry_type_for_payment(payment),
        payment_method=payment.payment_method,
        approval_status=TreasuryEntryApprovalStatus.POSTED,
        requires_approval=False,
        idempotency_key=f"payment:{payment.id}",
        amount=money(payment.amount),
        currency=payment.currency,
        occurred_at=occurred_at,
        description=description or f"{payment.purpose.value.replace('_', ' ').title()} {payment.provider_reference or str(payment.id)[:8]}",
        proof_reference=payment.proof_reference,
        proof_url=payment.proof_url,
        proof_notes=payment.proof_notes,
        external_reference=payment.provider_reference,
        payment_transaction_id=payment.id,
        loan_id=payment.loan_id,
        borrower_id=payment.borrower_id,
        recorded_by_user_id=payment.initiated_by_user_id,
    )
    db.add(entry)
    db.flush()
    recalculate_daily_ledger(db, ledger)
    return entry


def _active_entries(entries: Iterable[TreasuryEntry]) -> list[TreasuryEntry]:
    """Return entries that are allowed to affect balances and statements.

    Older in-memory/test objects may not have ``approval_status`` yet, so they
    are treated as posted. Database rows created by the new module always have
    the field explicitly populated.
    """
    allowed = {
        TreasuryEntryApprovalStatus.POSTED,
        TreasuryEntryApprovalStatus.APPROVED,
        TreasuryEntryApprovalStatus.POSTED.value,
        TreasuryEntryApprovalStatus.APPROVED.value,
    }
    return [
        entry
        for entry in entries
        if not getattr(entry, "is_voided", False)
        and getattr(entry, "approval_status", TreasuryEntryApprovalStatus.POSTED) in allowed
    ]


def _channel_totals(entries: Iterable[TreasuryEntry]) -> dict[str, dict[str, str | int]]:
    totals: dict[str, dict[str, Decimal | int]] = defaultdict(lambda: {
        "money_in": Decimal("0.00"),
        "money_out": Decimal("0.00"),
        "entry_count": 0,
    })
    for entry in _active_entries(entries):
        bucket = totals[entry.payment_method.value]
        if entry.direction == TreasuryDirection.MONEY_IN:
            bucket["money_in"] = money(bucket["money_in"] + money(entry.amount))
        else:
            bucket["money_out"] = money(bucket["money_out"] + money(entry.amount))
        bucket["entry_count"] = int(bucket["entry_count"]) + 1
    return {
        method: {
            "money_in": str(money(values["money_in"])),
            "money_out": str(money(values["money_out"])),
            "net": str(money(Decimal(str(values["money_in"])) - Decimal(str(values["money_out"])))),
            "entry_count": int(values["entry_count"]),
        }
        for method, values in totals.items()
    }


def _expense_totals(entries: Iterable[TreasuryEntry]) -> dict[str, str]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for entry in _active_entries(entries):
        if entry.entry_type == TreasuryEntryType.EXPENSE:
            key = str(entry.expense_category_id or "uncategorised")
            totals[key] += money(entry.amount)
    return {key: str(money(value)) for key, value in totals.items()}


def _opening_source_totals(sources: Iterable[BranchOpeningSource]) -> dict[str, str]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for source in sources:
        if source.is_voided or not source.is_confirmed:
            continue
        totals[source.source_type.value] += money(source.amount)
    return {key: str(money(value)) for key, value in totals.items()}


def submit_daily_ledger(
    db: Session,
    ledger: BranchDailyLedger,
    *,
    user_id: UUID | None,
    declared_closing_balance: Decimal | None,
    notes: str | None,
    automatic: bool,
) -> BranchDailySubmission:
    if ledger.status not in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        raise HTTPException(status_code=409, detail="This branch day has already been submitted")
    recalculate_daily_ledger(db, ledger)
    entries = db.query(TreasuryEntry).filter(TreasuryEntry.daily_ledger_id == ledger.id).all()
    sources = db.query(BranchOpeningSource).filter(BranchOpeningSource.daily_ledger_id == ledger.id).all()
    previous_sequence = db.query(func.coalesce(func.max(BranchDailySubmission.sequence_number), 0)).filter(
        BranchDailySubmission.daily_ledger_id == ledger.id
    ).scalar()
    settings = get_or_create_settings(db, ledger.company_id)
    now = datetime.now(timezone.utc)
    declared = money(declared_closing_balance) if declared_closing_balance is not None else None
    variance = money((declared if declared is not None else ledger.expected_closing_balance) - ledger.expected_closing_balance)
    unresolved_note = None
    if ledger.pending_entry_count:
        unresolved_note = f"{ledger.pending_entry_count} expense(s) were still pending approval and excluded from the submitted totals."
    combined_notes = "\n".join(filter(None, [(notes or "").strip() or None, unresolved_note])) or None
    submission = BranchDailySubmission(
        daily_ledger_id=ledger.id,
        company_id=ledger.company_id,
        branch_id=ledger.branch_id,
        submitted_to_branch_id=settings.headquarters_branch_id,
        business_date=ledger.business_date,
        sequence_number=int(previous_sequence or 0) + 1,
        is_automatic=automatic,
        opening_balance=money(ledger.opening_balance),
        total_money_in=money(ledger.total_money_in),
        total_money_out=money(ledger.total_money_out),
        closing_balance=money(ledger.expected_closing_balance),
        declared_closing_balance=declared,
        variance_amount=variance,
        entry_count=ledger.entry_count,
        pending_entry_count=ledger.pending_entry_count,
        channel_totals=_channel_totals(entries),
        expense_totals=_expense_totals(entries),
        opening_source_totals=_opening_source_totals(sources),
        submitted_at=now,
        submitted_by_user_id=user_id,
        notes=combined_notes,
    )
    db.add(submission)
    ledger.status = TreasuryDayStatus.AUTO_SUBMITTED if automatic else TreasuryDayStatus.SUBMITTED
    ledger.submitted_at = now
    ledger.auto_submitted_at = now if automatic else ledger.auto_submitted_at
    ledger.submitted_by_user_id = user_id
    ledger.declared_closing_balance = declared
    ledger.variance_amount = variance
    ledger.notes = combined_notes
    db.flush()
    from services.branch_submission_report_service import ensure_branch_submission_pdf
    ensure_branch_submission_pdf(db, submission)
    return submission


def issue_branch_funding(
    db: Session,
    *,
    company_id: UUID,
    target_branch_id: UUID,
    amount: Decimal,
    payment_method: PaymentMethod,
    business_date: date,
    user_id: UUID,
    proof_reference: str | None,
    proof_url: str | None,
    notes: str | None,
) -> BranchFundingTransfer:
    settings = get_or_create_settings(db, company_id)
    source = headquarters_branch(db, company_id)
    if not source:
        raise HTTPException(status_code=409, detail="Configure an active headquarters branch before issuing branch funds")
    target = db.get(CompanyBranch, target_branch_id)
    if not target or target.company_id != company_id or not target.is_active:
        raise HTTPException(status_code=404, detail="The destination branch was not found")
    if target.id == source.id:
        raise HTTPException(status_code=422, detail="Headquarters cannot issue branch funding to itself")
    validate_manual_proof(settings, payment_method, proof_reference, proof_url)
    amount_value = money(amount)
    if amount_value <= 0:
        raise HTTPException(status_code=422, detail="Branch funding must be greater than zero")

    source_ledger = get_or_create_daily_ledger(db, company_id=company_id, branch_id=source.id, business_date=business_date)
    target_ledger = get_or_create_daily_ledger(db, company_id=company_id, branch_id=target.id, business_date=business_date)
    assert_ledger_writable(source_ledger)
    assert_ledger_writable(target_ledger)
    reference = f"BFT-{business_date:%Y%m%d}-{secrets.token_hex(4).upper()}"
    transfer = BranchFundingTransfer(
        company_id=company_id,
        source_branch_id=source.id,
        target_branch_id=target.id,
        business_date=business_date,
        amount=amount_value,
        currency=settings.currency,
        payment_method=payment_method,
        reference=reference,
        status=BranchTransferStatus.ISSUED,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        notes=(notes or "").strip() or None,
        issued_at=datetime.now(timezone.utc),
        issued_by_user_id=user_id,
    )
    db.add(transfer)
    db.flush()
    outgoing = TreasuryEntry(
        company_id=company_id,
        branch_id=source.id,
        daily_ledger_id=source_ledger.id,
        direction=TreasuryDirection.MONEY_OUT,
        entry_type=TreasuryEntryType.BRANCH_FUNDING,
        payment_method=payment_method,
        approval_status=TreasuryEntryApprovalStatus.POSTED,
        idempotency_key=f"transfer-out:{transfer.id}",
        amount=amount_value,
        currency=settings.currency,
        occurred_at=transfer.issued_at,
        description=f"Morning funding issued to {target.name}",
        proof_reference=transfer.proof_reference,
        proof_url=transfer.proof_url,
        proof_notes=transfer.notes,
        external_reference=reference,
        transfer_id=transfer.id,
        counterparty_branch_id=target.id,
        recorded_by_user_id=user_id,
    )
    db.add(outgoing)
    opening_source = BranchOpeningSource(
        company_id=company_id,
        branch_id=target.id,
        daily_ledger_id=target_ledger.id,
        source_type=OpeningSourceType.HEADQUARTERS_FUNDING,
        payment_method=payment_method,
        amount=amount_value,
        currency=settings.currency,
        description=f"Morning funding from {source.name}",
        source_reference=reference,
        proof_reference=transfer.proof_reference,
        proof_url=transfer.proof_url,
        proof_notes=transfer.notes,
        transfer_id=transfer.id,
        is_system_generated=True,
        is_confirmed=False,
        recorded_by_user_id=user_id,
    )
    db.add(opening_source)
    db.flush()
    recalculate_daily_ledger(db, source_ledger)
    recalculate_daily_ledger(db, target_ledger)
    return transfer


def receive_branch_funding(db: Session, transfer: BranchFundingTransfer, user_id: UUID) -> BranchFundingTransfer:
    if transfer.status == BranchTransferStatus.RECEIVED:
        return transfer
    if transfer.status != BranchTransferStatus.ISSUED:
        raise HTTPException(status_code=409, detail="This branch funding transfer cannot be received")
    source = db.query(BranchOpeningSource).filter(BranchOpeningSource.transfer_id == transfer.id).first()
    if not source:
        raise HTTPException(status_code=409, detail="The matched branch opening source is missing")
    ledger = source.daily_ledger or db.get(BranchDailyLedger, source.daily_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="The destination branch day was not found")
    assert_ledger_writable(ledger)
    now = datetime.now(timezone.utc)
    source.is_confirmed = True
    source.confirmed_at = now
    source.confirmed_by_user_id = user_id
    transfer.status = BranchTransferStatus.RECEIVED
    transfer.received_at = now
    transfer.received_by_user_id = user_id
    recalculate_daily_ledger(db, ledger)
    return transfer


def void_treasury_entry(db: Session, entry: TreasuryEntry, *, user_id: UUID, reason: str) -> TreasuryEntry:
    ledger = entry.daily_ledger or db.get(BranchDailyLedger, entry.daily_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_ledger_writable(ledger)
    if entry.is_voided:
        return entry
    entry.is_voided = True
    entry.void_reason = reason.strip()
    entry.voided_at = datetime.now(timezone.utc)
    entry.voided_by_user_id = user_id
    if not entry.payment_transaction_id:
        from services.accounting_service import reverse_reference_accounting
        reverse_reference_accounting(
            db, company_id=entry.company_id, branch_id=entry.branch_id,
            reference_type="treasury_entry", reference_id=str(entry.id),
            user_id=user_id, reason=reason.strip(),
        )
    recalculate_daily_ledger(db, ledger)
    return entry


def reopen_daily_ledger(db: Session, ledger: BranchDailyLedger, *, reason: str) -> BranchDailyLedger:
    if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        return ledger
    ledger.status = TreasuryDayStatus.REOPENED
    ledger.notes = "\n".join(filter(None, [ledger.notes, f"Reopened: {reason.strip()}"]))
    ledger.reviewed_at = None
    ledger.reviewed_by_user_id = None
    db.flush()
    return ledger


def method_totals_for_entries(
    entries: Iterable[TreasuryEntry],
    opening_sources: Iterable[BranchOpeningSource] | None = None,
) -> list[dict[str, object]]:
    raw = _channel_totals(entries)
    opening_by_method: dict[PaymentMethod, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for source in opening_sources or []:
        if source.is_voided or not source.is_confirmed:
            continue
        opening_by_method[source.payment_method] = money(opening_by_method[source.payment_method] + money(source.amount))

    rows: list[dict[str, object]] = []
    for method in PaymentMethod:
        values = raw.get(method.value, {"money_in": "0.00", "money_out": "0.00", "net": "0.00", "entry_count": 0})
        opening = money(opening_by_method[method])
        movement = money(values["net"])
        rows.append({
            "method": method,
            "opening_balance": opening,
            "money_in": money(values["money_in"]),
            "money_out": money(values["money_out"]),
            "net": movement,
            "closing_balance": money(opening + movement),
            "entry_count": int(values["entry_count"]),
        })
    return rows


def opening_source_totals_for_sources(sources: Iterable[BranchOpeningSource]) -> list[dict[str, object]]:
    totals: dict[OpeningSourceType, Decimal] = defaultdict(lambda: Decimal("0.00"))
    counts: dict[OpeningSourceType, int] = defaultdict(int)
    for source in sources:
        if source.is_voided or not source.is_confirmed:
            continue
        totals[source.source_type] += money(source.amount)
        counts[source.source_type] += 1
    return [
        {"source_type": source_type, "amount": money(totals[source_type]), "source_count": counts[source_type]}
        for source_type in OpeningSourceType
    ]


def build_dashboard(
    db: Session,
    company_id: UUID,
    business_date: date,
    *,
    branch_id: UUID | None = None,
) -> dict[str, object]:
    settings = get_or_create_settings(db, company_id)
    branch_query = db.query(CompanyBranch).filter(
        CompanyBranch.company_id == company_id,
        CompanyBranch.is_active.is_(True),
    )
    if branch_id:
        branch_query = branch_query.filter(CompanyBranch.id == branch_id)
    branches = branch_query.order_by(
        CompanyBranch.is_headquarters.desc(),
        CompanyBranch.name.asc(),
    ).all()
    ledgers: list[BranchDailyLedger] = []
    for branch in branches:
        ledger = get_or_create_daily_ledger(db, company_id=company_id, branch_id=branch.id, business_date=business_date)
        if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
            recalculate_daily_ledger(db, ledger)
        ledgers.append(ledger)
    ledger_ids = [ledger.id for ledger in ledgers]
    entries = db.query(TreasuryEntry).filter(TreasuryEntry.daily_ledger_id.in_(ledger_ids or [None])).all()
    sources = db.query(BranchOpeningSource).filter(BranchOpeningSource.daily_ledger_id.in_(ledger_ids or [None])).all()
    branch_map = {branch.id: branch for branch in branches}
    source_rows = opening_source_totals_for_sources(sources)
    source_map = {row["source_type"]: money(row["amount"]) for row in source_rows}
    previous_closing = source_map.get(OpeningSourceType.PREVIOUS_CLOSING, Decimal("0.00"))
    owner_contributions = source_map.get(OpeningSourceType.OWNER_CONTRIBUTION, Decimal("0.00"))
    headquarters_funding = source_map.get(OpeningSourceType.HEADQUARTERS_FUNDING, Decimal("0.00"))
    total_opening = money(sum((money(ledger.opening_balance) for ledger in ledgers), Decimal("0.00")))
    total_in = money(sum((money(ledger.total_money_in) for ledger in ledgers), Decimal("0.00")))
    total_out = money(sum((money(ledger.total_money_out) for ledger in ledgers), Decimal("0.00")))
    internal_transfer_out = money(sum(
        (money(entry.amount) for entry in _active_entries(entries) if entry.entry_type == TreasuryEntryType.BRANCH_FUNDING),
        Decimal("0.00"),
    ))
    external_money_out = money(total_out - internal_transfer_out)
    known = previous_closing + owner_contributions + headquarters_funding
    pending_expense_amount = money(sum(
        (money(entry.amount) for entry in entries if not entry.is_voided and entry.entry_type == TreasuryEntryType.EXPENSE and entry.approval_status == TreasuryEntryApprovalStatus.PENDING),
        Decimal("0.00"),
    ))
    return {
        "business_date": business_date,
        "currency": settings.currency,
        "headquarters_branch_id": settings.headquarters_branch_id,
        "auto_open_enabled": settings.auto_open_enabled,
        "auto_open_time": settings.auto_open_time,
        "auto_submit_enabled": settings.auto_submit_enabled,
        "auto_submit_time": settings.auto_submit_time,
        "consolidated_previous_closing": money(previous_closing),
        "owner_contributions": money(owner_contributions),
        "headquarters_funding": money(headquarters_funding),
        "other_opening_sources": money(total_opening - known),
        "total_opening_balance": total_opening,
        "total_money_in": total_in,
        "total_money_out": total_out,
        "internal_transfer_out": internal_transfer_out,
        "external_money_out": external_money_out,
        "consolidated_closing_balance": money(total_opening + total_in - total_out),
        "pending_expense_amount": pending_expense_amount,
        "method_totals": method_totals_for_entries(entries, sources),
        "opening_source_totals": source_rows,
        "branches": [
            {
                "branch_id": ledger.branch_id,
                "branch_name": branch_map[ledger.branch_id].name,
                "is_headquarters": branch_map[ledger.branch_id].is_headquarters,
                "ledger_id": ledger.id,
                "status": ledger.status,
                "opening_balance": money(ledger.opening_balance),
                "total_money_in": money(ledger.total_money_in),
                "total_money_out": money(ledger.total_money_out),
                "expected_closing_balance": money(ledger.expected_closing_balance),
                "declared_closing_balance": money(ledger.declared_closing_balance) if ledger.declared_closing_balance is not None else None,
                "variance_amount": money(ledger.variance_amount),
                "entry_count": ledger.entry_count,
                "pending_entry_count": ledger.pending_entry_count,
                "submitted_at": ledger.submitted_at,
            }
            for ledger in ledgers
        ],
    }


def statement_entries(
    db: Session,
    *,
    company_id: UUID,
    date_from: date,
    date_to: date,
    branch_id: UUID | None = None,
    methods: list[PaymentMethod] | None = None,
    directions: list[TreasuryDirection] | None = None,
) -> tuple[list[TreasuryEntry], Decimal]:
    query = (
        db.query(TreasuryEntry)
        .join(BranchDailyLedger, BranchDailyLedger.id == TreasuryEntry.daily_ledger_id)
        .options(joinedload(TreasuryEntry.expense_category))
        .filter(
            TreasuryEntry.company_id == company_id,
            TreasuryEntry.is_voided.is_(False),
            _posted_entry_filter(),
            BranchDailyLedger.business_date >= date_from,
            BranchDailyLedger.business_date <= date_to,
        )
    )
    if branch_id:
        query = query.filter(TreasuryEntry.branch_id == branch_id)
    if methods:
        query = query.filter(TreasuryEntry.payment_method.in_(methods))
    if directions:
        query = query.filter(TreasuryEntry.direction.in_(directions))
    entries = query.order_by(TreasuryEntry.occurred_at.asc(), TreasuryEntry.created_at.asc()).all()
    opening_query = db.query(func.coalesce(func.sum(BranchDailyLedger.opening_balance), 0)).filter(
        BranchDailyLedger.company_id == company_id,
        BranchDailyLedger.business_date == date_from,
    )
    if branch_id:
        opening_query = opening_query.filter(BranchDailyLedger.branch_id == branch_id)
    return entries, money(opening_query.scalar())


def build_statement(
    db: Session,
    *,
    company_id: UUID,
    date_from: date,
    date_to: date,
    branch_id: UUID | None = None,
    methods: list[PaymentMethod] | None = None,
    directions: list[TreasuryDirection] | None = None,
) -> dict[str, object]:
    entries, opening = statement_entries(
        db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
        methods=methods,
        directions=directions,
    )
    total_in = money(sum((money(row.amount) for row in entries if row.direction == TreasuryDirection.MONEY_IN), Decimal("0.00")))
    total_out = money(sum((money(row.amount) for row in entries if row.direction == TreasuryDirection.MONEY_OUT), Decimal("0.00")))
    return {
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": opening,
        "total_money_in": total_in,
        "total_money_out": total_out,
        "closing_balance": money(opening + total_in - total_out),
        "method_totals": method_totals_for_entries(entries),
        "entries": entries,
    }


def statement_csv(statement: dict[str, object], branch_names: dict[UUID, str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["LoanHub money movement statement"])
    writer.writerow(["Date from", statement["date_from"]])
    writer.writerow(["Date to", statement["date_to"]])
    writer.writerow(["Opening balance", statement["opening_balance"]])
    writer.writerow(["Money in", statement["total_money_in"]])
    writer.writerow(["Money out", statement["total_money_out"]])
    writer.writerow(["Closing balance", statement["closing_balance"]])
    writer.writerow([])
    writer.writerow(["Occurred at", "Branch", "Direction", "Entry type", "Payment method", "Approval", "Voucher", "Amount", "Currency", "Description", "Proof reference", "External reference"])
    for entry in statement["entries"]:  # type: ignore[index]
        writer.writerow([
            entry.occurred_at.isoformat(),
            branch_names.get(entry.branch_id, str(entry.branch_id)),
            entry.direction.value,
            entry.entry_type.value,
            PAYMENT_METHOD_LABELS[entry.payment_method],
            entry.approval_status.value,
            entry.voucher_number or "",
            entry.amount,
            entry.currency,
            entry.description,
            entry.proof_reference or "",
            entry.external_reference or "",
        ])
    return buffer.getvalue()


def auto_open_due_ledgers(db: Session, now_utc: datetime | None = None, company_id: UUID | None = None) -> int:
    now = now_utc or datetime.now(timezone.utc)
    opened = 0
    query = db.query(TreasurySettings).filter(TreasurySettings.auto_open_enabled.is_(True))
    if company_id:
        query = query.filter(TreasurySettings.company_id == company_id)
    for settings in query.all():
        local_now = now.astimezone(resolve_timezone(settings.timezone))
        if local_now.time().replace(tzinfo=None) < settings.auto_open_time:
            continue
        branches = db.query(CompanyBranch).filter(
            CompanyBranch.company_id == settings.company_id,
            CompanyBranch.is_active.is_(True),
        ).all()
        for branch in branches:
            existing = db.query(BranchDailyLedger.id).filter(
                BranchDailyLedger.company_id == settings.company_id,
                BranchDailyLedger.branch_id == branch.id,
                BranchDailyLedger.business_date == local_now.date(),
            ).first()
            ledger = get_or_create_daily_ledger(
                db,
                company_id=settings.company_id,
                branch_id=branch.id,
                business_date=local_now.date(),
            )
            recalculate_daily_ledger(db, ledger)
            if not existing:
                opened += 1
    if opened:
        db.commit()
    return opened


def auto_submit_due_ledgers(db: Session, now_utc: datetime | None = None, company_id: UUID | None = None) -> int:
    """Create the scheduled 16:30 snapshot and finalise older reopened days.

    The configured cut-off is an accountable snapshot, not a permanent block on
    later customer payments. A payment received after an automatic snapshot can
    reopen the live day through ``ensure_current_payment_day_writable``. The
    scheduler will not create another same-day automatic snapshot, but when the
    date rolls over it submits the reopened prior day again as a final sequence.
    """
    now = now_utc or datetime.now(timezone.utc)
    submitted = 0
    query = db.query(TreasurySettings).filter(TreasurySettings.auto_submit_enabled.is_(True))
    if company_id:
        query = query.filter(TreasurySettings.company_id == company_id)

    for settings in query.all():
        local_now = now.astimezone(resolve_timezone(settings.timezone))
        due_ledgers = (
            db.query(BranchDailyLedger)
            .filter(
                BranchDailyLedger.company_id == settings.company_id,
                BranchDailyLedger.status.in_([TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED]),
                BranchDailyLedger.business_date <= local_now.date(),
            )
            .all()
        )

        for ledger in {row.id: row for row in due_ledgers}.values():
            is_prior_day = ledger.business_date < local_now.date()
            is_cutoff_due = (
                ledger.business_date == local_now.date()
                and local_now.time().replace(tzinfo=None) >= settings.auto_submit_time
                and ledger.auto_submitted_at is None
            )
            if not is_prior_day and not is_cutoff_due:
                continue

            submit_daily_ledger(
                db,
                ledger,
                user_id=None,
                declared_closing_balance=None,
                notes=(
                    "Automatic scheduled branch snapshot at the configured submission cut-off."
                    if is_cutoff_due
                    else "Automatic final submission after the local business date rolled over."
                ),
                automatic=True,
            )
            submitted += 1

    if submitted:
        db.commit()
    return submitted


def run_treasury_cycle(db: Session, now_utc: datetime | None = None) -> tuple[int, int]:
    opened = auto_open_due_ledgers(db, now_utc=now_utc)
    submitted = auto_submit_due_ledgers(db, now_utc=now_utc)
    return opened, submitted
