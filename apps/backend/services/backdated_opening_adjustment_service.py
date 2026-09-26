from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.enums import OpeningSourceType, PaymentMethod, TreasuryDayStatus
from database.models.treasury import BranchDailyLedger, BranchOpeningSource, BranchDailySubmission
from services.accounting_service import account_by_code, create_entry, ensure_chart, scope_key
from services.treasury_service import (
    _ensure_previous_closing_source,
    get_or_create_daily_ledger,
    get_or_create_settings,
    local_business_date,
    money,
    recalculate_daily_ledger,
    reopen_daily_ledger,
    submit_daily_ledger,
)


BLOCKED_SOURCE_TYPES = {
    OpeningSourceType.PREVIOUS_CLOSING,
    OpeningSourceType.HEADQUARTERS_FUNDING,
}
LOCKED_DAY_STATUSES = {
    TreasuryDayStatus.SUBMITTED,
    TreasuryDayStatus.AUTO_SUBMITTED,
    TreasuryDayStatus.REVIEWED,
}


@dataclass(slots=True)
class BackdatedOpeningAdjustmentResult:
    source: BranchOpeningSource
    target_ledger: BranchDailyLedger
    old_opening_balance: Decimal
    new_opening_balance: Decimal
    old_expected_closing_balance: Decimal
    new_expected_closing_balance: Decimal
    target_submission_sequence: int | None
    downstream_days_refreshed: int
    downstream_days_revised: int
    current_opening_balance: Decimal | None
    current_expected_closing_balance: Decimal | None


def _post_historical_opening_source_accounting(
    db: Session,
    source: BranchOpeningSource,
) -> None:
    """Post the opening source through normal accounting, even for a closed period.

    Back-dated opening corrections are privileged historical corrections. They
    must still create a balanced journal entry, but an already-closed accounting
    period cannot prevent the correction from being represented in the books.
    """
    if source.source_type in BLOCKED_SOURCE_TYPES:
        return

    key, _ = scope_key(source.company_id)
    ensure_chart(db, company_id=source.company_id)
    debit_account = account_by_code(db, key, "1000")
    credit_code = "3000" if source.source_type == OpeningSourceType.OWNER_CONTRIBUTION else "3100"
    credit_account = account_by_code(db, key, credit_code)
    create_entry(
        db,
        company_id=source.company_id,
        branch_id=source.branch_id,
        created_by_user_id=source.recorded_by_user_id,
        entry_date=source.daily_ledger.business_date,
        description=f"Historical opening correction: {source.description}",
        reference_type="opening_source",
        reference_id=str(source.id),
        status_value="posted",
        allow_closed_period=True,
        lines=[
            {"account_id": debit_account.id, "debit": source.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": source.amount},
        ],
    )


def _latest_submission(db: Session, ledger_id: UUID) -> BranchDailySubmission | None:
    return (
        db.query(BranchDailySubmission)
        .filter(BranchDailySubmission.daily_ledger_id == ledger_id)
        .order_by(
            BranchDailySubmission.sequence_number.desc(),
            BranchDailySubmission.submitted_at.desc(),
        )
        .first()
    )


def _resubmit_revised_day(
    db: Session,
    ledger: BranchDailyLedger,
    *,
    user_id: UUID,
    reason: str,
    declared_closing_balance: Decimal | None,
) -> BranchDailySubmission:
    return submit_daily_ledger(
        db,
        ledger,
        user_id=user_id,
        declared_closing_balance=declared_closing_balance,
        notes=f"Historical opening correction revision: {reason.strip()}",
        automatic=False,
    )


def _refresh_downstream_ledgers(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID,
    after_date: date,
    user_id: UUID,
    reason: str,
) -> tuple[int, int]:
    """Refresh carry-forward balances after a historical correction.

    Open/reopened days can be recalculated directly. Submitted days are revised
    without deleting the earlier submission: the previous declared physical
    close is preserved as an audit anchor when one exists, while days without a
    declared close inherit the corrected calculated balance.
    """
    rows = (
        db.query(BranchDailyLedger)
        .filter(
            BranchDailyLedger.company_id == company_id,
            BranchDailyLedger.branch_id == branch_id,
            BranchDailyLedger.business_date > after_date,
        )
        .order_by(BranchDailyLedger.business_date.asc())
        .all()
    )
    refreshed = 0
    revised = 0
    for ledger in rows:
        original_status = ledger.status
        prior_declared = ledger.declared_closing_balance
        was_locked = original_status in LOCKED_DAY_STATUSES

        if was_locked:
            reopen_daily_ledger(
                db,
                ledger,
                reason=(
                    "Carry-forward recalculation after historical opening correction. "
                    f"Source date {after_date.isoformat()}: {reason.strip()}"
                ),
            )

        # Rebuild only the system previous-closing source. All genuine sources
        # and movements on the downstream day remain untouched.
        _ensure_previous_closing_source(db, ledger)
        recalculate_daily_ledger(db, ledger)
        refreshed += 1

        if was_locked:
            _resubmit_revised_day(
                db,
                ledger,
                user_id=user_id,
                reason=(
                    f"Carry-forward revised from historical opening correction dated {after_date.isoformat()}. "
                    f"{reason.strip()}"
                ),
                declared_closing_balance=(
                    money(prior_declared) if prior_declared is not None else None
                ),
            )
            revised += 1

    return refreshed, revised


def create_backdated_opening_adjustment(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    business_date: date,
    source_type: OpeningSourceType,
    payment_method: PaymentMethod,
    amount: Decimal,
    currency: str,
    description: str,
    correction_reason: str,
    source_reference: str | None = None,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    corrected_declared_closing_balance: Decimal | None = None,
) -> BackdatedOpeningAdjustmentResult:
    settings = get_or_create_settings(db, company_id)
    today = local_business_date(settings)
    if business_date >= today:
        raise HTTPException(
            status_code=422,
            detail=(
                "A back-dated opening adjustment must use a business date before today. "
                "Use the normal Opening sources workflow for today's funds."
            ),
        )
    if source_type in BLOCKED_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Previous closing and headquarters funding are system-controlled opening sources",
        )

    amount_value = money(amount)
    if amount_value <= 0:
        raise HTTPException(status_code=422, detail="The historical opening amount must be greater than zero")

    reason = correction_reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=422, detail="Enter a correction reason of at least 10 characters")
    description_value = description.strip()
    if len(description_value) < 3:
        raise HTTPException(status_code=422, detail="Describe the historical source of funds")

    ledger = get_or_create_daily_ledger(
        db,
        company_id=company_id,
        branch_id=branch_id,
        business_date=business_date,
    )
    old_opening = money(ledger.opening_balance)
    old_expected = money(ledger.expected_closing_balance)
    original_status = ledger.status
    prior_declared = ledger.declared_closing_balance
    was_locked = original_status in LOCKED_DAY_STATUSES

    if was_locked:
        reopen_daily_ledger(
            db,
            ledger,
            reason=f"Back-dated opening correction: {reason}",
        )

    reference = (source_reference or "").strip() or (
        f"BACKDATED-OPENING:{business_date.isoformat()}:{secrets.token_hex(5).upper()}"
    )
    duplicate = (
        db.query(BranchOpeningSource.id)
        .filter(
            BranchOpeningSource.daily_ledger_id == ledger.id,
            BranchOpeningSource.source_type == source_type,
            BranchOpeningSource.source_reference == reference,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="That historical opening source reference is already recorded")

    now = datetime.now(timezone.utc)
    audit_notes = "\n".join(
        filter(
            None,
            [
                (proof_notes or "").strip() or None,
                f"Back-dated correction reason: {reason}",
                f"Recorded at {now.isoformat()}",
            ],
        )
    )
    source = BranchOpeningSource(
        company_id=company_id,
        branch_id=branch_id,
        daily_ledger_id=ledger.id,
        source_type=source_type,
        payment_method=payment_method,
        amount=amount_value,
        currency=currency.upper(),
        description=description_value,
        source_reference=reference,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        proof_notes=audit_notes,
        is_system_generated=False,
        is_confirmed=True,
        confirmed_at=now,
        confirmed_by_user_id=user_id,
        recorded_by_user_id=user_id,
    )
    db.add(source)
    db.flush()
    _post_historical_opening_source_accounting(db, source)
    recalculate_daily_ledger(db, ledger)

    target_submission_sequence: int | None = None
    if was_locked:
        declared_for_revision = corrected_declared_closing_balance
        if declared_for_revision is None and prior_declared is not None:
            # A physical closing count is evidence. Preserve it unless the user
            # explicitly supplies the corrected physical close in this action.
            declared_for_revision = money(prior_declared)
        submission = _resubmit_revised_day(
            db,
            ledger,
            user_id=user_id,
            reason=reason,
            declared_closing_balance=declared_for_revision,
        )
        target_submission_sequence = submission.sequence_number

    downstream_refreshed, downstream_revised = _refresh_downstream_ledgers(
        db,
        company_id=company_id,
        branch_id=branch_id,
        after_date=business_date,
        user_id=user_id,
        reason=reason,
    )

    current = (
        db.query(BranchDailyLedger)
        .filter(
            BranchDailyLedger.company_id == company_id,
            BranchDailyLedger.branch_id == branch_id,
            BranchDailyLedger.business_date == today,
        )
        .first()
    )
    return BackdatedOpeningAdjustmentResult(
        source=source,
        target_ledger=ledger,
        old_opening_balance=old_opening,
        new_opening_balance=money(ledger.opening_balance),
        old_expected_closing_balance=old_expected,
        new_expected_closing_balance=money(ledger.expected_closing_balance),
        target_submission_sequence=target_submission_sequence,
        downstream_days_refreshed=downstream_refreshed,
        downstream_days_revised=downstream_revised,
        current_opening_balance=(money(current.opening_balance) if current is not None else None),
        current_expected_closing_balance=(money(current.expected_closing_balance) if current is not None else None),
    )
