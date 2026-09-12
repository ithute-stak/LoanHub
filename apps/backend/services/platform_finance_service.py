from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database.models.finance import (
    BorrowerFeeConfiguration,
    CompanyAccountOpeningFeeConfiguration,
    PlatformChargeClaim,
    TransactionChargeAgreement,
    TransactionChargeLedgerEntry,
)
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import (
    LoanRequestStatus,
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.loan_request import LoanRequest
from database.models.payment import PaymentTransaction


MONEY = Decimal("0.01")
NON_CHARGEABLE_PURPOSES = {
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE,
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
    PaymentPurpose.BORROW_REQUEST_FEE,
    PaymentPurpose.PLATFORM_FEE,
}


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def active_borrower_fee_configuration(
    db: Session,
    *,
    company_id: UUID | None = None,
    at: datetime | None = None,
) -> BorrowerFeeConfiguration | None:
    moment = at or datetime.now(timezone.utc)
    query = db.query(BorrowerFeeConfiguration).filter(
        BorrowerFeeConfiguration.is_active.is_(True),
        or_(
            BorrowerFeeConfiguration.effective_from.is_(None),
            BorrowerFeeConfiguration.effective_from <= moment,
        ),
        or_(
            BorrowerFeeConfiguration.effective_to.is_(None),
            BorrowerFeeConfiguration.effective_to >= moment,
        ),
    )
    if company_id:
        override = (
            query.filter(BorrowerFeeConfiguration.company_id == company_id)
            .order_by(BorrowerFeeConfiguration.created_at.desc())
            .first()
        )
        if override:
            return override
    return (
        query.filter(BorrowerFeeConfiguration.company_id.is_(None))
        .order_by(BorrowerFeeConfiguration.created_at.desc())
        .first()
    )


def calculate_borrower_fee(config: BorrowerFeeConfiguration, requested_amount: Decimal) -> Decimal:
    requested = Decimal(requested_amount)
    value = Decimal("0")
    if config.fee_type in {"flat", "hybrid"}:
        value += Decimal(config.flat_amount or 0)
    if config.fee_type in {"percentage", "hybrid"}:
        value += requested * Decimal(config.percentage or 0) / Decimal("100")
    if config.minimum_amount is not None:
        value = max(value, Decimal(config.minimum_amount))
    if config.maximum_amount is not None:
        value = min(value, Decimal(config.maximum_amount))
    return money(value)


def apply_fee_snapshot_to_request(
    db: Session,
    loan_request: LoanRequest,
    *,
    company_id: UUID | None = None,
) -> BorrowerFeeConfiguration | None:
    config = active_borrower_fee_configuration(db, company_id=company_id)
    if not config:
        loan_request.service_fee_amount = Decimal("0")
        loan_request.service_fee_currency = "LSL"
        loan_request.service_fee_status = "not_required"
        return None
    loan_request.service_fee_amount = calculate_borrower_fee(config, Decimal(loan_request.requested_amount))
    loan_request.service_fee_currency = config.currency
    loan_request.service_fee_status = (
        "required" if config.required_before_submission and loan_request.service_fee_amount > 0 else "not_required"
    )
    return config


def finalize_borrow_request_fee(db: Session, payment: PaymentTransaction) -> None:
    if payment.purpose != PaymentPurpose.BORROW_REQUEST_FEE or not payment.loan_request_id:
        return
    request = (
        db.query(LoanRequest)
        .filter(LoanRequest.id == payment.loan_request_id)
        .with_for_update()
        .first()
    )
    if not request:
        return
    if payment.status == PaymentStatus.SUCCEEDED:
        request.service_fee_status = "paid"
        request.service_fee_payment_id = payment.id
        now = datetime.now(timezone.utc)
        request.submitted_at = request.submitted_at or now
        if request.visible_to_lenders:
            request.status = LoanRequestStatus.OPEN
            request.expires_at = request.expires_at or (now + timedelta(days=30))
        elif request.status == LoanRequestStatus.DRAFT:
            request.status = LoanRequestStatus.SUBMITTED
    elif payment.status == PaymentStatus.FAILED:
        request.service_fee_status = "failed"
        request.service_fee_payment_id = payment.id



def active_company_account_opening_fee_configuration(
    db: Session,
    *,
    company_id: UUID | None = None,
    at: datetime | None = None,
) -> CompanyAccountOpeningFeeConfiguration | None:
    moment = at or datetime.now(timezone.utc)
    query = db.query(CompanyAccountOpeningFeeConfiguration).filter(
        CompanyAccountOpeningFeeConfiguration.is_active.is_(True),
        or_(
            CompanyAccountOpeningFeeConfiguration.effective_from.is_(None),
            CompanyAccountOpeningFeeConfiguration.effective_from <= moment,
        ),
        or_(
            CompanyAccountOpeningFeeConfiguration.effective_to.is_(None),
            CompanyAccountOpeningFeeConfiguration.effective_to >= moment,
        ),
    )
    if company_id:
        override = (
            query.filter(CompanyAccountOpeningFeeConfiguration.company_id == company_id)
            .order_by(CompanyAccountOpeningFeeConfiguration.created_at.desc())
            .first()
        )
        if override:
            return override
    return (
        query.filter(CompanyAccountOpeningFeeConfiguration.company_id.is_(None))
        .order_by(CompanyAccountOpeningFeeConfiguration.created_at.desc())
        .first()
    )


def calculate_company_account_opening_fee(
    config: CompanyAccountOpeningFeeConfiguration | None,
    base_amount: Decimal = Decimal("0"),
) -> Decimal:
    if config is None:
        return Decimal("0.00")
    value = Decimal("0")
    if config.fee_type in {"flat", "hybrid"}:
        value += Decimal(config.flat_amount or 0)
    if config.fee_type in {"percentage", "hybrid"}:
        value += Decimal(base_amount or 0) * Decimal(config.percentage or 0) / Decimal("100")
    if config.minimum_amount is not None:
        value = max(value, Decimal(config.minimum_amount))
    if config.maximum_amount is not None:
        value = min(value, Decimal(config.maximum_amount))
    return money(value)


def apply_company_account_opening_fee_snapshot(
    account: CompanyBorrowerAccount,
    *,
    fee_config: CompanyAccountOpeningFeeConfiguration | None,
) -> None:
    if not fee_config:
        account.opening_fee_configuration_id = None
        account.opening_fee_amount = Decimal("0")
        account.opening_fee_currency = "LSL"
        account.opening_fee_status = "not_required"
        account.status = "active"
        return
    amount = calculate_company_account_opening_fee(fee_config)
    account.opening_fee_configuration_id = fee_config.id
    account.opening_fee_amount = amount
    account.opening_fee_currency = fee_config.currency
    account.opening_fee_status = "accrued" if amount > 0 else "not_required"
    account.status = "active"


def finalize_company_borrower_account_fee(db: Session, payment: PaymentTransaction) -> None:
    if (
        payment.purpose != PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE
        or not payment.company_borrower_account_id
    ):
        return
    account = (
        db.query(CompanyBorrowerAccount)
        .filter(CompanyBorrowerAccount.id == payment.company_borrower_account_id)
        .with_for_update()
        .first()
    )
    if not account:
        return
    account.opening_fee_payment_id = payment.id
    if payment.status == PaymentStatus.SUCCEEDED:
        account.opening_fee_status = "paid"
        account.status = "active"
        if account.borrower and account.borrower.user:
            account.borrower.user.is_active = True
    elif payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
        account.opening_fee_status = payment.status.value
        account.status = "payment_failed"
    else:
        account.opening_fee_status = payment.status.value
        account.status = "pending_fee"

def active_charge_agreement(
    db: Session,
    company_id: UUID,
    *,
    at: date | None = None,
) -> TransactionChargeAgreement | None:
    day = at or datetime.now(timezone.utc).date()
    return (
        db.query(TransactionChargeAgreement)
        .filter(
            TransactionChargeAgreement.company_id == company_id,
            TransactionChargeAgreement.status == "active",
            TransactionChargeAgreement.effective_from <= day,
            or_(
                TransactionChargeAgreement.effective_to.is_(None),
                TransactionChargeAgreement.effective_to >= day,
            ),
        )
        .order_by(TransactionChargeAgreement.effective_from.desc())
        .first()
    )


def calculate_transaction_charge(
    agreement: TransactionChargeAgreement,
    direction: PaymentDirection,
    gross_amount: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    if direction == PaymentDirection.INBOUND:
        percentage = Decimal(agreement.inbound_percentage or 0)
        flat = Decimal(agreement.inbound_flat_fee or 0)
    else:
        percentage = Decimal(agreement.outbound_percentage or 0)
        flat = Decimal(agreement.outbound_flat_fee or 0)
    value = Decimal(gross_amount) * percentage / Decimal("100") + flat
    if agreement.minimum_charge is not None:
        value = max(value, Decimal(agreement.minimum_charge))
    if agreement.maximum_charge is not None:
        value = min(value, Decimal(agreement.maximum_charge))
    return percentage, money(flat), money(value)


def accrue_platform_transaction_charge(
    db: Session,
    payment: PaymentTransaction,
) -> TransactionChargeLedgerEntry | None:
    if (
        payment.status != PaymentStatus.SUCCEEDED
        or not payment.company_id
        or payment.purpose in NON_CHARGEABLE_PURPOSES
    ):
        return None
    existing = (
        db.query(TransactionChargeLedgerEntry)
        .filter(TransactionChargeLedgerEntry.payment_id == payment.id)
        .first()
    )
    if existing:
        return existing
    agreement = active_charge_agreement(db, payment.company_id)
    if not agreement:
        return None
    percentage, flat, charge = calculate_transaction_charge(
        agreement,
        payment.direction,
        Decimal(payment.amount),
    )
    if charge <= 0:
        return None
    entry = TransactionChargeLedgerEntry(
        company_id=payment.company_id,
        agreement_id=agreement.id,
        payment_id=payment.id,
        direction=payment.direction,
        provider=payment.provider,
        payment_purpose=payment.purpose.value,
        gross_amount=money(payment.amount),
        percentage_rate=percentage,
        flat_fee=flat,
        charge_amount=charge,
        currency=payment.currency,
        status="accrued",
        accrued_at=payment.completed_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


def agreement_number() -> str:
    return f"AGR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def claim_number() -> str:
    return f"CLM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def create_charge_claim(
    db: Session,
    *,
    company_id: UUID,
    period_start: date,
    period_end: date,
    due_days: int,
    issued_by_user_id: UUID,
    notes: str | None = None,
) -> PlatformChargeClaim:
    agreement = active_charge_agreement(db, company_id, at=period_end)
    if not agreement:
        raise HTTPException(status_code=409, detail="The company has no active transaction-charge agreement")
    rows = (
        db.query(TransactionChargeLedgerEntry)
        .filter(
            TransactionChargeLedgerEntry.company_id == company_id,
            TransactionChargeLedgerEntry.agreement_id == agreement.id,
            TransactionChargeLedgerEntry.status == "accrued",
            TransactionChargeLedgerEntry.accrued_at >= datetime.combine(period_start, datetime.min.time()),
            TransactionChargeLedgerEntry.accrued_at < datetime.combine(period_end + timedelta(days=1), datetime.min.time()),
        )
        .with_for_update()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail="No unclaimed transaction charges exist for the selected period")
    now = datetime.now(timezone.utc)
    claim = PlatformChargeClaim(
        company_id=company_id,
        agreement_id=agreement.id,
        claim_number=claim_number(),
        period_start=period_start,
        period_end=period_end,
        transaction_count=len(rows),
        gross_transaction_value=money(sum((Decimal(row.gross_amount) for row in rows), Decimal("0"))),
        amount=money(sum((Decimal(row.charge_amount) for row in rows), Decimal("0"))),
        currency=agreement.currency,
        status="issued",
        issued_at=now,
        due_at=now + timedelta(days=due_days),
        issued_by_user_id=issued_by_user_id,
        notes=notes,
    )
    db.add(claim)
    db.flush()
    for row in rows:
        row.claim_id = claim.id
        row.status = "claimed"
        row.claimed_at = now
    return claim


def finalize_claim_settlement(db: Session, payment: PaymentTransaction) -> None:
    if payment.purpose != PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT:
        return
    claim = (
        db.query(PlatformChargeClaim)
        .filter(PlatformChargeClaim.payment_id == payment.id)
        .with_for_update()
        .first()
    )
    if not claim:
        return
    if payment.status == PaymentStatus.SUCCEEDED:
        now = payment.completed_at or datetime.now(timezone.utc)
        claim.status = "paid"
        claim.paid_at = now
        rows = db.query(TransactionChargeLedgerEntry).filter(
            TransactionChargeLedgerEntry.claim_id == claim.id
        ).all()
        for row in rows:
            row.status = "settled"
            row.settled_at = now
    elif payment.status == PaymentStatus.FAILED and claim.status == "payment_pending":
        claim.status = "issued"


def finalize_cash_finance_payment(db: Session, payment: PaymentTransaction) -> None:
    finalize_borrow_request_fee(db, payment)
    finalize_company_borrower_account_fee(db, payment)
    finalize_claim_settlement(db, payment)
    accrue_platform_transaction_charge(db, payment)


def record_claim_settlement(
    db: Session,
    *,
    claim: PlatformChargeClaim,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
):
    """Settle a platform charge claim with a verified payment method.

    Electronic channels are evidence-based until a live adapter is enabled.
    Cash creates a physical cash row; all other methods require a reference or
    document proving the transfer.
    """
    from database.models.cash import CashTransaction
    from services.accounting_service import record_payment_accounting
    from services.receipt_service import ensure_payment_receipt

    if claim.status not in {"issued", "acknowledged", "disputed"}:
        raise HTTPException(status_code=409, detail="This claim is not available for settlement")
    if Decimal(claim.amount or 0) <= 0:
        raise HTTPException(status_code=409, detail="This claim does not have a payable amount")
    if payment_method != PaymentMethod.CASH and not (
        (proof_reference or "").strip() or (proof_url or "").strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="A proof reference or proof document is required for a non-cash settlement",
        )

    key = idempotency_key or f"claim-settlement:{claim.id}:{secrets.token_hex(6)}"
    existing = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == key).first()
    if existing:
        return existing, existing.cash_transaction

    now = datetime.now(timezone.utc)
    prefix = "COUT" if payment_method == PaymentMethod.CASH else "POUT"
    reference = f"{prefix}-{payment_method.value.upper()}-{now:%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"
    payment = PaymentTransaction(
        company_id=claim.company_id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.CASH if payment_method == PaymentMethod.CASH else PaymentProvider.MANUAL,
        payment_method=payment_method,
        direction=PaymentDirection.OUTBOUND,
        purpose=PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
        status=PaymentStatus.SUCCEEDED,
        amount=money(claim.amount),
        currency=claim.currency,
        idempotency_key=key,
        provider_reference=reference,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        proof_notes=(proof_notes or notes or "").strip() or None,
        verified_by_user_id=initiated_by_user_id,
        verified_at=now,
        provider_payload={
            "method": payment_method.value,
            "claim_id": str(claim.id),
            "evidence_based": payment_method != PaymentMethod.CASH,
            "notes": notes,
        },
        completed_at=now,
    )
    db.add(payment)
    db.flush()

    cash = None
    if payment_method == PaymentMethod.CASH:
        cash = CashTransaction(
            payment_id=payment.id,
            branch_id=None,
            handled_by_user_id=initiated_by_user_id,
            direction=PaymentDirection.OUTBOUND,
            cash_reference=reference,
            tendered_amount=payment.amount,
            applied_amount=payment.amount,
            change_amount=0,
            forward_amount=0,
            notes=notes or f"Cash settlement for platform claim {claim.claim_number}",
        )
        db.add(cash)

    claim.payment_id = payment.id
    finalize_claim_settlement(db, payment)
    record_payment_accounting(db, payment)
    ensure_payment_receipt(db, payment)
    from services.treasury_service import record_payment_treasury_entry

    record_payment_treasury_entry(
        db,
        payment,
        description=f"Platform claim settlement {claim.claim_number}",
    )
    db.commit()
    db.refresh(payment)
    if cash:
        db.refresh(cash)
    return payment, cash


def record_cash_claim_settlement(
    db: Session,
    *,
    claim: PlatformChargeClaim,
    initiated_by_user_id: UUID,
    notes: str | None = None,
    idempotency_key: str | None = None,
):
    """Backward-compatible cash-only wrapper."""
    return record_claim_settlement(
        db,
        claim=claim,
        initiated_by_user_id=initiated_by_user_id,
        payment_method=PaymentMethod.CASH,
        notes=notes,
        idempotency_key=idempotency_key,
    )
