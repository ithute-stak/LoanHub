from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.cash import CashTransaction
from database.models.client_loan_company import ClientCompanyLoan
from database.models.early_settlement import LoanEarlySettlement
from database.models.enums import (
    InstallmentStatus,
    LoanCalculationMethod,
    LoanStatus,
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from services.interest_calculation_service import (
    calculate_daily_accrued_interest,
    calculate_loan_terms,
    generate_monthly_due_dates,
    normalize_interest_method,
)


MONEY = Decimal("0.01")
MONTHLY_SETTLEMENT_METHODS = {
    LoanCalculationMethod.MICRO_LOAN,
    LoanCalculationMethod.SIMPLE_INTEREST,
    LoanCalculationMethod.FLAT_RATE,
    LoanCalculationMethod.COMPOUND_INTEREST,
    LoanCalculationMethod.REDUCING_BALANCE,
}


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def settlement_interest_start(loan: ClientCompanyLoan) -> date:
    raw = (loan.calculation_breakdown or {}).get("interest_start_date")
    if raw:
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            pass
    if loan.disbursed_at:
        return loan.disbursed_at.date()
    raise HTTPException(status_code=409, detail="The loan does not have a recorded interest start date")


def settlement_due_dates(loan: ClientCompanyLoan) -> list[date]:
    rows = sorted(
        (
            item for item in loan.installments
            if not getattr(item, "is_superseded", False)
        ),
        key=lambda item: item.installment_number,
    )
    dates = [item.due_date for item in rows]
    if dates:
        return dates
    return generate_monthly_due_dates(
        settlement_interest_start(loan),
        int(loan.repayment_period),
    )


def chargeable_months(
    *,
    settlement_date: date,
    start_date: date,
    due_dates: list[date],
    original_term_months: int,
) -> int:
    if settlement_date < start_date:
        raise ValueError("Settlement date cannot be before the loan interest start date")
    periods = 1
    for due_date in due_dates[:-1]:
        if settlement_date > due_date:
            periods += 1
    return min(max(periods, 1), max(original_term_months, 1))


def calculate_method_earned_interest(
    *,
    method: LoanCalculationMethod | str,
    principal: Decimal,
    rate_percent: Decimal,
    original_term_months: int,
    start_date: date,
    due_dates: list[date],
    settlement_date: date,
) -> tuple[Decimal, int, dict[str, Any]]:
    """Apply the loan's own calculator to the actual settlement period."""
    resolved = normalize_interest_method(method)
    periods = chargeable_months(
        settlement_date=settlement_date,
        start_date=start_date,
        due_dates=due_dates,
        original_term_months=original_term_months,
    )
    if resolved == LoanCalculationMethod.DAILY_ACCRUAL_REDUCING:
        interest, segments = calculate_daily_accrued_interest(
            principal,
            rate_percent,
            start_date,
            settlement_date,
        )
        return money(interest), periods, {
            "basis": "actual_days_on_outstanding_principal",
            "start_date": start_date.isoformat(),
            "settlement_date": settlement_date.isoformat(),
            "segments": segments,
        }

    shortened_dates = due_dates[:periods]
    if len(shortened_dates) < periods:
        shortened_dates = generate_monthly_due_dates(start_date, periods)
    _, _, details = calculate_loan_terms(
        principal=principal,
        rate_percent=rate_percent,
        term_months=periods,
        processing_fee=Decimal("0"),
        interest_method=resolved,
        start_date=start_date,
        due_dates=shortened_dates,
    )
    return money(details["total_interest"]), periods, {
        "basis": "same_calculator_shortened_term",
        "calculator": resolved.value,
        "chargeable_periods": periods,
        "recalculation": details,
    }


def _successful_repayments(
    db: Session,
    loan: ClientCompanyLoan,
) -> list[PaymentTransaction]:
    return (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.loan_id == loan.id,
            PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        .order_by(PaymentTransaction.completed_at.asc(), PaymentTransaction.created_at.asc())
        .all()
    )


def _payment_components(
    db: Session,
    payment: PaymentTransaction,
) -> tuple[Decimal, Decimal, Decimal]:
    principal = Decimal("0")
    interest = Decimal("0")
    fees = Decimal("0")
    rows = (
        db.query(PaymentAllocation, RepaymentInstallment)
        .join(RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id)
        .filter(PaymentAllocation.payment_id == payment.id)
        .all()
    )
    for allocation, installment in rows:
        amount = money(allocation.amount)
        total = money(installment.total_due)
        if total <= 0:
            principal += amount
            continue
        principal += money(amount * money(installment.principal_due) / total)
        interest += money(amount * money(installment.interest_due) / total)
        fees += money(amount * money(installment.fee_due) / total)
    difference = money(payment.amount) - money(principal + interest + fees)
    principal = money(principal + difference)
    return money(principal), money(interest), money(fees)


def _daily_interest_with_actual_payments(
    db: Session,
    loan: ClientCompanyLoan,
    repayments: list[PaymentTransaction],
    *,
    start_date: date,
    settlement_date: date,
) -> tuple[Decimal, list[dict[str, Any]]]:
    balance = money(loan.principal_amount)
    cursor = start_date
    total = Decimal("0")
    audit_segments: list[dict[str, Any]] = []
    for payment in repayments:
        moment = payment.completed_at or payment.created_at
        payment_date = moment.date()
        if payment_date > settlement_date:
            break
        segment_end = max(payment_date, cursor)
        interest, segments = calculate_daily_accrued_interest(
            balance,
            loan.interest_rate,
            cursor,
            segment_end,
        )
        total += interest
        principal_paid, _, _ = _payment_components(db, payment)
        audit_segments.append({
            "from": cursor.isoformat(),
            "to": segment_end.isoformat(),
            "opening_principal": str(balance),
            "interest": str(interest),
            "principal_payment": str(principal_paid),
            "segments": segments,
        })
        balance = money(max(balance - principal_paid, Decimal("0")))
        cursor = segment_end
    if cursor < settlement_date:
        interest, segments = calculate_daily_accrued_interest(
            balance,
            loan.interest_rate,
            cursor,
            settlement_date,
        )
        total += interest
        audit_segments.append({
            "from": cursor.isoformat(),
            "to": settlement_date.isoformat(),
            "opening_principal": str(balance),
            "interest": str(interest),
            "principal_payment": "0.00",
            "segments": segments,
        })
    return money(total), audit_segments


def _installment_snapshot(loan: ClientCompanyLoan) -> list[dict[str, Any]]:
    return [
        {
            "id": str(item.id),
            "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            "paid_amount": str(money(item.paid_amount)),
            "paid_at": item.paid_at.isoformat() if item.paid_at else None,
            "is_superseded": bool(item.is_superseded),
            "superseded_at": item.superseded_at.isoformat() if item.superseded_at else None,
        }
        for item in loan.installments
    ]


def quote_early_settlement(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    settlement_date: date,
    quoted_by_user_id: UUID,
    valid_for_days: int = 3,
) -> LoanEarlySettlement:
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="Only an active or defaulted loan can be settled early")
    today = date.today()
    if settlement_date < today:
        raise HTTPException(status_code=422, detail="Settlement quotes cannot be backdated")
    if settlement_date > today + timedelta(days=30):
        raise HTTPException(status_code=422, detail="Settlement quotes cannot be dated more than 30 days ahead")

    start_date = settlement_interest_start(loan)
    if settlement_date < start_date:
        raise HTTPException(status_code=422, detail="Settlement date cannot precede the interest start date")

    processing = (
        db.query(LoanEarlySettlement)
        .filter(
            LoanEarlySettlement.loan_id == loan.id,
            LoanEarlySettlement.status == "processing",
        )
        .first()
    )
    if processing:
        raise HTTPException(status_code=409, detail="This loan already has a settlement payment in progress")

    now = datetime.now(timezone.utc)
    (
        db.query(LoanEarlySettlement)
        .filter(
            LoanEarlySettlement.loan_id == loan.id,
            LoanEarlySettlement.status == "quoted",
        )
        .update({"status": "expired"}, synchronize_session=False)
    )

    repayments = _successful_repayments(db, loan)
    ledger_received = money(sum((money(item.amount) for item in repayments), Decimal("0")))
    payments_received = money(loan.amount_paid)
    if abs(ledger_received - payments_received) > MONEY:
        raise HTTPException(
            status_code=409,
            detail=(
                "The loan balance and successful repayment ledger do not reconcile. "
                "Reconcile the loan before issuing an early-settlement quote."
            ),
        )
    paid_principal = Decimal("0")
    paid_interest = Decimal("0")
    paid_fees = Decimal("0")
    for payment in repayments:
        principal_part, interest_part, fee_part = _payment_components(db, payment)
        paid_principal += principal_part
        paid_interest += interest_part
        paid_fees += fee_part
    paid_principal, paid_interest, paid_fees = map(money, (paid_principal, paid_interest, paid_fees))

    method = normalize_interest_method(loan.calculation_method)
    due_dates = settlement_due_dates(loan)
    if method == LoanCalculationMethod.DAILY_ACCRUAL_REDUCING:
        earned_interest, daily_segments = _daily_interest_with_actual_payments(
            db,
            loan,
            repayments,
            start_date=start_date,
            settlement_date=settlement_date,
        )
        periods = chargeable_months(
            settlement_date=settlement_date,
            start_date=start_date,
            due_dates=due_dates,
            original_term_months=int(loan.repayment_period),
        )
        method_details = {
            "basis": "actual_days_on_actual_outstanding_principal",
            "segments": daily_segments,
        }
    else:
        earned_interest, periods, method_details = calculate_method_earned_interest(
            method=method,
            principal=money(loan.principal_amount),
            rate_percent=money(loan.interest_rate),
            original_term_months=int(loan.repayment_period),
            start_date=start_date,
            due_dates=due_dates,
            settlement_date=settlement_date,
        )

    original_interest = money(
        (loan.calculation_breakdown or {}).get("total_interest")
        or sum((money(item.interest_due) for item in loan.installments), Decimal("0"))
    )
    retained_fee = money(loan.processing_fee)
    revised_total = money(money(loan.principal_amount) + earned_interest + retained_fee)
    settlement_amount = money(max(revised_total - payments_received, Decimal("0")))
    credit = money(max(payments_received - revised_total, Decimal("0")))

    remaining = settlement_amount
    fee_due = min(money(max(retained_fee - paid_fees, Decimal("0"))), remaining)
    remaining = money(remaining - fee_due)
    interest_due = min(money(max(earned_interest - paid_interest, Decimal("0"))), remaining)
    remaining = money(remaining - interest_due)
    principal_due = remaining

    quote = LoanEarlySettlement(
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_id=loan.id,
        quoted_by_user_id=quoted_by_user_id,
        status="quoted",
        settlement_date=settlement_date,
        quote_expires_at=now + timedelta(days=valid_for_days),
        calculation_method=method.value,
        original_term_months=int(loan.repayment_period),
        chargeable_periods=periods,
        original_maturity_date=loan.maturity_date,
        original_principal=money(loan.principal_amount),
        original_total_repayable=money(loan.total_repayable),
        original_balance=money(loan.balance),
        original_amount_paid=money(loan.amount_paid),
        original_total_interest=original_interest,
        earned_interest=earned_interest,
        unearned_interest_rebate=money(max(original_interest - earned_interest, Decimal("0"))),
        processing_fee_retained=retained_fee,
        payments_received=payments_received,
        revised_total_repayable=revised_total,
        settlement_amount=settlement_amount,
        settlement_principal=principal_due,
        settlement_interest=interest_due,
        settlement_fees=fee_due,
        overpayment_credit=credit,
        calculation_snapshot={
            "original": loan.calculation_breakdown or {},
            "settlement": method_details,
            "paid_components": {
                "principal": str(paid_principal),
                "interest": str(paid_interest),
                "fees": str(paid_fees),
            },
            "loan_snapshot": {
                "status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
                "total_repayable": str(money(loan.total_repayable)),
                "amount_paid": str(money(loan.amount_paid)),
                "balance": str(money(loan.balance)),
                "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None,
                "repayment_period": int(loan.repayment_period),
                "installment_amount": str(money(loan.installment_amount)),
                "calculation_breakdown": loan.calculation_breakdown or {},
            },
        },
        installment_snapshot=_installment_snapshot(loan),
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def _quote_from_payment(db: Session, payment: PaymentTransaction) -> LoanEarlySettlement | None:
    raw = (payment.provider_payload or {}).get("early_settlement_id")
    if not raw:
        return None
    try:
        return db.get(LoanEarlySettlement, UUID(str(raw)))
    except ValueError:
        return None


def assert_no_settlement_in_progress(db: Session, loan_id: UUID) -> None:
    exists = (
        db.query(LoanEarlySettlement.id)
        .filter(
            LoanEarlySettlement.loan_id == loan_id,
            LoanEarlySettlement.status == "processing",
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail="An early-settlement payment is already processing for this loan",
        )


def finalize_early_settlement_payment(
    db: Session,
    payment: PaymentTransaction,
) -> LoanEarlySettlement:
    referenced_quote = _quote_from_payment(db, payment)
    if not referenced_quote:
        raise HTTPException(status_code=409, detail="Early-settlement payment is missing its quote")
    quote = (
        db.query(LoanEarlySettlement)
        .filter(LoanEarlySettlement.id == referenced_quote.id)
        .with_for_update()
        .first()
    )
    if not quote:
        raise HTTPException(status_code=409, detail="Early-settlement quote no longer exists")
    if quote.status == "settled":
        return quote
    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(status_code=409, detail="Settlement cannot finalize before confirmed payment success")

    loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == quote.loan_id)
        .with_for_update()
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Settlement loan was not found")
    if money(payment.amount) != money(quote.settlement_amount):
        raise HTTPException(status_code=409, detail="Settlement payment does not match the signed quote")
    if money(loan.amount_paid) != money(quote.original_amount_paid):
        raise HTTPException(
            status_code=409,
            detail="The loan changed after this quote; create a new early-settlement quote",
        )

    now = payment.completed_at or datetime.now(timezone.utc)
    for installment in loan.installments:
        if installment.status != InstallmentStatus.PAID:
            installment.status = InstallmentStatus.WAIVED
            installment.is_superseded = True
            installment.superseded_at = now

    loan.total_repayable = money(quote.revised_total_repayable)
    loan.amount_paid = money(quote.revised_total_repayable)
    loan.balance = Decimal("0.00")
    loan.status = LoanStatus.COMPLETED
    loan.repayment_period = quote.chargeable_periods
    loan.installment_amount = money(
        quote.revised_total_repayable / Decimal(max(quote.chargeable_periods, 1))
    )
    loan.maturity_date = quote.settlement_date
    loan.calculation_breakdown = {
        **(loan.calculation_breakdown or {}),
        "early_settlement": {
            "settlement_id": str(quote.id),
            "settlement_date": quote.settlement_date.isoformat(),
            "original_total_repayable": str(quote.original_total_repayable),
            "revised_total_repayable": str(quote.revised_total_repayable),
            "earned_interest": str(quote.earned_interest),
            "unearned_interest_rebate": str(quote.unearned_interest_rebate),
            "chargeable_periods": quote.chargeable_periods,
            "method": quote.calculation_method,
        },
    }

    quote.payment_id = payment.id
    quote.status = "settled"
    quote.settled_at = now
    quote.settled_by_user_id = payment.initiated_by_user_id

    from services.accounting_service import record_payment_accounting
    from services.platform_finance_service import accrue_platform_transaction_charge
    from services.receipt_service import ensure_payment_receipt
    from services.treasury_service import record_payment_treasury_entry

    record_payment_accounting(db, payment)
    accrue_platform_transaction_charge(db, payment)
    ensure_payment_receipt(db, payment)
    branch_id = (payment.provider_payload or {}).get("branch_id")
    record_payment_treasury_entry(
        db,
        payment,
        branch_id=UUID(branch_id) if branch_id else loan.branch_id,
        description=f"Early settlement {loan.loan_reference}",
    )
    return quote


def initiate_early_settlement_payment(
    db: Session,
    *,
    quote: LoanEarlySettlement,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod,
    borrower_acknowledged: bool,
    agreement_note: str,
    agreement_reference: str | None,
    notes: str | None,
    idempotency_key: str | None,
    gateway_provider: str | None = None,
    gateway_customer_phone: str | None = None,
) -> PaymentTransaction:
    quote_id = quote.id
    quote = (
        db.query(LoanEarlySettlement)
        .filter(LoanEarlySettlement.id == quote_id)
        .with_for_update()
        .first()
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Early-settlement quote not found")

    key = idempotency_key or f"early-settlement:{quote.id}"
    existing = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.idempotency_key == key)
        .first()
    )
    if existing:
        linked_quote = _quote_from_payment(db, existing)
        if linked_quote and linked_quote.id == quote.id:
            return existing
        raise HTTPException(status_code=409, detail="Idempotency key belongs to another payment")
    if quote.status != "quoted":
        raise HTTPException(status_code=409, detail="This settlement quote is no longer payable")

    now = datetime.now(timezone.utc)
    expires_at = quote.quote_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        quote.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="The early-settlement quote has expired")
    if not borrower_acknowledged:
        raise HTTPException(status_code=422, detail="Borrower acknowledgement is required")
    if len(agreement_note.strip()) < 3:
        raise HTTPException(status_code=422, detail="Record the settlement agreement or acknowledgement")
    if money(quote.settlement_amount) <= 0:
        raise HTTPException(
            status_code=409,
            detail="No payment is due; the overpayment credit requires a controlled refund workflow",
        )
    if payment_method not in {PaymentMethod.CASH, PaymentMethod.LELEFAPAYGATE}:
        raise HTTPException(status_code=422, detail="Use Cash or LelefaPayGate for early settlement")

    loan = db.get(ClientCompanyLoan, quote.loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Settlement loan was not found")
    if money(loan.amount_paid) != money(quote.original_amount_paid):
        raise HTTPException(status_code=409, detail="The loan changed after this quote; create a new quote")

    quote.borrower_acknowledged = True
    quote.agreement_note = agreement_note.strip()
    quote.agreement_reference = (agreement_reference or "").strip() or None
    quote.status = "processing"
    db.add(quote)
    db.commit()

    integration_context = {
        "early_settlement_id": str(quote.id),
        "branch_id": str(loan.branch_id) if loan.branch_id else None,
    }
    if payment_method == PaymentMethod.LELEFAPAYGATE:
        from services.lelefa_paygate_service import initiate_gateway_payment

        try:
            payment = initiate_gateway_payment(
                db,
                purpose=PaymentPurpose.LOAN_REPAYMENT,
                amount=money(quote.settlement_amount),
                idempotency_key=key,
                initiated_by_user_id=initiated_by_user_id,
                company_id=loan.company_id,
                borrower_id=loan.borrower_id,
                loan_request_id=loan.loan_request_id,
                loan_id=loan.id,
                branch_id=loan.branch_id,
                reference=f"{loan.loan_reference}-SETTLEMENT",
                integration_context=integration_context,
                gateway_provider=gateway_provider,
                payer_phone=gateway_customer_phone,
            )
        except HTTPException:
            quote.status = "failed"
            db.add(quote)
            db.commit()
            raise
        quote.payment_id = payment.id
        if payment.status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
            quote.status = "failed"
        db.add(quote)
        db.commit()
        db.refresh(payment)
        return payment

    reference = f"CIN-SETTLEMENT-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"
    payment = PaymentTransaction(
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.CASH,
        payment_method=PaymentMethod.CASH,
        direction=PaymentDirection.INBOUND,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        status=PaymentStatus.SUCCEEDED,
        amount=money(quote.settlement_amount),
        currency="LSL",
        idempotency_key=key,
        provider_reference=reference,
        verified_by_user_id=initiated_by_user_id,
        verified_at=now,
        completed_at=now,
        provider_payload={
            **integration_context,
            "method": "cash",
            "agreement_note": quote.agreement_note,
            "agreement_reference": quote.agreement_reference,
            "notes": notes,
        },
    )
    db.add(payment)
    db.flush()
    db.add(
        CashTransaction(
            payment_id=payment.id,
            branch_id=loan.branch_id,
            handled_by_user_id=initiated_by_user_id,
            direction=PaymentDirection.INBOUND,
            cash_reference=reference,
            tendered_amount=payment.amount,
            applied_amount=payment.amount,
            change_amount=0,
            forward_amount=0,
            notes=notes or "Early loan settlement",
        )
    )
    finalize_early_settlement_payment(db, payment)
    db.commit()
    db.refresh(payment)
    return payment


def reverse_early_settlement(
    db: Session,
    payment: PaymentTransaction,
) -> bool:
    quote = _quote_from_payment(db, payment)
    if not quote or quote.status != "settled":
        return False
    loan = db.get(ClientCompanyLoan, quote.loan_id)
    if not loan:
        return False
    snapshot = (quote.calculation_snapshot or {}).get("loan_snapshot", {})
    try:
        loan.status = LoanStatus(snapshot.get("status", "active"))
    except ValueError:
        loan.status = LoanStatus.ACTIVE
    loan.total_repayable = money(snapshot.get("total_repayable", quote.original_total_repayable))
    loan.amount_paid = money(snapshot.get("amount_paid", quote.original_amount_paid))
    loan.balance = money(snapshot.get("balance", quote.original_balance))
    loan.maturity_date = (
        date.fromisoformat(snapshot["maturity_date"])
        if snapshot.get("maturity_date")
        else quote.original_maturity_date
    )
    loan.repayment_period = int(snapshot.get("repayment_period", quote.original_term_months))
    loan.installment_amount = money(
        snapshot.get("installment_amount", loan.installment_amount)
    )
    loan.calculation_breakdown = snapshot.get("calculation_breakdown") or {}

    rows = {str(item.id): item for item in loan.installments}
    for state in quote.installment_snapshot or []:
        installment = rows.get(str(state.get("id")))
        if not installment:
            continue
        installment.status = InstallmentStatus(state["status"])
        installment.paid_amount = money(state["paid_amount"])
        installment.paid_at = datetime.fromisoformat(state["paid_at"]) if state.get("paid_at") else None
        installment.is_superseded = bool(state.get("is_superseded"))
        installment.superseded_at = (
            datetime.fromisoformat(state["superseded_at"])
            if state.get("superseded_at")
            else None
        )

    quote.status = "reversed"
    quote.reversed_at = datetime.now(timezone.utc)
    db.add(quote)
    return True
