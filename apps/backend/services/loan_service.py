from __future__ import annotations

import re
import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.cash import CashTransaction
from database.models.client_loan_company import ClientCompanyLoan
from database.models.origination import LoanContract, LoanTopUpSettlement, OriginationPolicy
from database.models.company import LoanCompany
from database.models.enums import (
    InstallmentStatus,
    LoanCalculationMethod,
    LoanRequestStatus,
    LoanStatus,
    OfferStatus,
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
    RepaymentType,
)
from database.models.loan_offer import LoanOffer
from database.models.loan_request import LoanRequest
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from services.accounting_service import record_payment_accounting
from services.interest_calculation_service import calculate_loan_terms
from utils.payment_dates import payment_date_to_utc


MONEY = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)



def calculate_micro_loan_totals(
    principal: Decimal,
    rate_percent: Decimal,
    term_months: int,
    processing_fee: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, dict[str, Any]]:
    """Calculate micro-loan amounts without creating repayment dates.

    This compatibility helper intentionally has no date logic. Repayment dates
    are supplied manually only when a real schedule is requested.
    """
    principal_value = money(principal)
    rate_value = Decimal(str(rate_percent or 0))
    fee_value = money(processing_fee or 0)
    if principal_value <= 0:
        raise ValueError("Principal must be greater than zero")
    if term_months <= 0 or term_months > 120:
        raise ValueError("Term months must be between 1 and 120")
    if rate_value < 0 or fee_value < 0:
        raise ValueError("Rate and processing fee cannot be negative")

    factor = Decimal("1") + (rate_value / Decimal("100"))
    running_balance = principal_value
    components: list[Decimal] = []
    steps: list[dict[str, Any]] = []
    for month_number in range(1, term_months + 1):
        opening_balance = running_balance
        amount_after_rate = money(opening_balance * factor)
        if month_number < term_months:
            component = money(amount_after_rate / Decimal("2"))
            carried_balance = money(amount_after_rate - component)
        else:
            component = amount_after_rate
            carried_balance = Decimal("0.00")
        components.append(component)
        steps.append({
            "month": month_number,
            "opening_balance": str(opening_balance),
            "amount_after_rate": str(amount_after_rate),
            "component_amount": str(component),
            "carried_balance": str(carried_balance),
        })
        running_balance = carried_balance

    total = money(sum(components, Decimal("0")) + fee_value)
    regular = money(total / Decimal(term_months))
    schedule_amounts = [regular for _ in range(term_months)]
    schedule_amounts[-1] = money(total - sum(schedule_amounts[:-1], Decimal("0")))
    return schedule_amounts[0], total, {
        "method": LoanCalculationMethod.MICRO_LOAN.value,
        "components": [str(value) for value in components],
        "steps": steps,
        "schedule_amounts": [str(value) for value in schedule_amounts],
    }


def calculate_offer_totals(
    principal: Decimal,
    annual_interest_rate: Decimal,
    term_months: int,
    processing_fee: Decimal,
    calculation_method: LoanCalculationMethod | str = LoanCalculationMethod.MICRO_LOAN,
    *,
    start_date: date | None = None,
    due_dates: list[date] | tuple[date, ...] | None = None,
) -> tuple[Decimal, Decimal, dict[str, Any]]:
    """Calculate offer terms with the same engine used by loans and contracts."""
    return calculate_loan_terms(
        principal=principal,
        rate_percent=annual_interest_rate,
        term_months=term_months,
        processing_fee=processing_fee,
        interest_method=calculation_method,
        start_date=start_date,
        due_dates=due_dates,
    )

LOAN_REFERENCE_PREFIX = "LB"
LOAN_REFERENCE_COMPANY_CODE_LENGTH = 3
LOAN_REFERENCE_TOKEN_LENGTH = 6
LOAN_REFERENCE_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _company_reference_code(name: str) -> str:
    """Return a stable three-character display code derived from a company name.

    Examples:
        Batlokoa Financial Services -> BFS
        Maseru Community Finance -> MCF
        LoanHub -> LOA

    The code is intentionally restricted to uppercase ASCII letters and digits
    so generated loan references remain safe for URLs, SMS messages, receipts
    and payment descriptions.
    """
    words = re.findall(r"[A-Z0-9]+", str(name or "").upper())
    if not words:
        return "XXX"

    if len(words) >= LOAN_REFERENCE_COMPANY_CODE_LENGTH:
        code = "".join(word[0] for word in words[:LOAN_REFERENCE_COMPANY_CODE_LENGTH])
    elif len(words) == 2:
        code = words[0][0] + words[1][:2]
    else:
        code = words[0][:LOAN_REFERENCE_COMPANY_CODE_LENGTH]

    padded = code.ljust(LOAN_REFERENCE_COMPANY_CODE_LENGTH, "X")
    return padded[:LOAN_REFERENCE_COMPANY_CODE_LENGTH]


def _loan_reference_token() -> str:
    return "".join(
        secrets.choice(LOAN_REFERENCE_ALPHABET)
        for _ in range(LOAN_REFERENCE_TOKEN_LENGTH)
    )


def generate_loan_reference(db: Session, company: LoanCompany | str) -> str:
    """Generate a compact LoanHub reference such as ``LBBFS8F3K29``.

    Existing legacy references remain valid; this format is used only for newly
    created loans. The database uniqueness check protects against random token
    collisions, while the model's unique constraint remains the final safeguard.
    """
    company_name = getattr(company, "name", None) or str(company)
    company_code = _company_reference_code(company_name)

    for _ in range(30):
        candidate = (
            f"{LOAN_REFERENCE_PREFIX}"
            f"{company_code}"
            f"{_loan_reference_token()}"
        )
        exists = (
            db.query(ClientCompanyLoan.id)
            .filter(ClientCompanyLoan.loan_reference == candidate)
            .first()
        )
        if not exists:
            return candidate
    raise HTTPException(status_code=503, detail="Could not generate a unique loan number")


def create_repayment_schedule(db: Session, loan: ClientCompanyLoan) -> None:
    if loan.installments:
        return

    breakdown = loan.calculation_breakdown or {}
    schedule_rows = breakdown.get("schedule_rows") or []

    if len(schedule_rows) != loan.repayment_period:
        raise HTTPException(
            status_code=409,
            detail=(
                "The repayment schedule has no complete set of manually entered installment due dates. "
                "Enter the dates before creating or approving the loan."
            ),
        )

    for raw in schedule_rows:
        db.add(
            RepaymentInstallment(
                loan_id=loan.id,
                installment_number=int(raw["installment_number"]),
                due_date=date.fromisoformat(str(raw["due_date"])),
                principal_due=money(raw["principal_due"]),
                interest_due=money(raw["interest_due"]),
                fee_due=money(raw.get("fee_due", 0)),
                total_due=money(raw["total_due"]),
                paid_amount=Decimal("0"),
                status=InstallmentStatus.PENDING,
            )
        )

    loan.first_payment_due = date.fromisoformat(str(schedule_rows[0]["due_date"]))
    loan.maturity_date = date.fromisoformat(str(schedule_rows[-1]["due_date"]))

def accept_offer(
    db: Session,
    *,
    request: LoanRequest,
    offer: LoanOffer,
    borrower_user_id: UUID,
) -> ClientCompanyLoan:
    if request.borrower.user_id != borrower_user_id:
        raise HTTPException(status_code=403, detail="This loan request does not belong to you")
    if offer.loan_request_id != request.id:
        raise HTTPException(status_code=400, detail="Offer does not belong to this request")
    if request.status in {LoanRequestStatus.ACCEPTED, LoanRequestStatus.CANCELLED}:
        raise HTTPException(status_code=409, detail="This request can no longer accept an offer")
    if offer.status != OfferStatus.PENDING:
        raise HTTPException(status_code=409, detail="This offer is no longer available")

    existing_loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.loan_request_id == request.id)
        .first()
    )
    if existing_loan:
        return existing_loan

    company = db.get(LoanCompany, offer.company_id)
    if not company:
        raise HTTPException(status_code=409, detail="The lending company is unavailable")

    now = datetime.now(timezone.utc)
    offer.status = OfferStatus.ACCEPTED
    offer.accepted_at = now
    request.status = LoanRequestStatus.ACCEPTED
    request.selected_offer_id = offer.id
    request.accepted_at = now
    request.visible_to_lenders = False

    competing_offers = (
        db.query(LoanOffer)
        .filter(
            LoanOffer.loan_request_id == request.id,
            LoanOffer.id != offer.id,
            LoanOffer.status == OfferStatus.PENDING,
        )
        .with_for_update()
        .all()
    )
    for competing_offer in competing_offers:
        competing_offer.status = OfferStatus.REJECTED

    loan = ClientCompanyLoan(
        loan_request_id=request.id,
        loan_offer_id=offer.id,
        company_id=offer.company_id,
        branch_id=offer.branch_id,
        borrower_id=request.borrower_id,
        loan_reference=generate_loan_reference(db, company),
        origination_channel=request.origination_channel or "online",
        principal_amount=offer.approved_amount,
        interest_rate=offer.interest_rate_percent or 0,
        processing_fee=offer.processing_fee or 0,
        total_repayable=offer.total_repayment,
        repayment_type=RepaymentType.MONTHLY,
        repayment_period=offer.term_months,
        installment_amount=offer.monthly_repayment,
        calculation_method=offer.calculation_method or "micro_loan",
        calculation_breakdown=offer.calculation_breakdown or {},
        approved_at=now,
        approved_by_user_id=offer.offered_by_user_id,
        amount_paid=0,
        balance=offer.total_repayment,
        status=LoanStatus.APPROVED,
    )
    db.add(loan)
    db.flush()
    create_repayment_schedule(db, loan)
    db.commit()
    db.refresh(loan)
    return loan


def _cash_reference(direction: PaymentDirection) -> str:
    prefix = "CIN" if direction == PaymentDirection.INBOUND else "COUT"
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def _payment_idempotency_key(prefix: str, supplied: str | None = None) -> str:
    return supplied or f"{prefix}:{uuid.uuid4()}"


def _first_open_installment(loan: ClientCompanyLoan) -> RepaymentInstallment | None:
    return next(
        (
            installment
            for installment in sorted(loan.installments, key=lambda item: item.installment_number)
            if not getattr(installment, "is_superseded", False)
            and installment.status
            in {
                InstallmentStatus.PENDING,
                InstallmentStatus.PARTIALLY_PAID,
                InstallmentStatus.OVERDUE,
            }
        ),
        None,
    )


def early_settlement_required_for_payoff(
    loan: ClientCompanyLoan,
    *,
    amount_applied: Decimal,
    as_of_date: date | None = None,
) -> tuple[bool, int]:
    """Detect a contractual payoff that still contains future instalment interest."""
    if money(amount_applied) < money(loan.balance):
        return False, 0

    effective_date = as_of_date or date.today()
    future_installments = 0
    for installment in loan.installments:
        if getattr(installment, "is_superseded", False):
            continue
        if installment.status not in {
            InstallmentStatus.PENDING,
            InstallmentStatus.PARTIALLY_PAID,
            InstallmentStatus.OVERDUE,
        }:
            continue
        outstanding = money(Decimal(installment.total_due) - Decimal(installment.paid_amount))
        if outstanding > 0 and installment.due_date > effective_date:
            future_installments += 1
    return future_installments > 0, future_installments


def preview_cash_repayment(
    loan: ClientCompanyLoan,
    *,
    amount_tendered: Decimal,
    overpayment_action: str,
    installment_number: int | None = None,
    payment_date: date | None = None,
) -> dict[str, Any]:
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="This loan is not accepting repayments")

    current = _first_open_installment(loan)
    if not current:
        raise HTTPException(status_code=409, detail="This loan has no unpaid installment")
    if installment_number is not None and installment_number != current.installment_number:
        raise HTTPException(
            status_code=409,
            detail=f"Installment {current.installment_number} must be cleared before another installment",
        )

    tendered = money(amount_tendered)
    outstanding = money(Decimal(current.total_due) - Decimal(current.paid_amount))
    loan_balance = money(loan.balance)

    if tendered <= outstanding:
        applied = tendered
        change = Decimal("0.00")
        forward = Decimal("0.00")
    elif overpayment_action == "give_change":
        applied = outstanding
        change = money(tendered - outstanding)
        forward = Decimal("0.00")
    else:
        applied = min(tendered, loan_balance)
        change = money(max(tendered - applied, Decimal("0")))
        forward = money(max(applied - outstanding, Decimal("0")))

    remaining_current = money(max(outstanding - applied, Decimal("0")))
    remaining_to_simulate = applied
    installments_covered = 0
    for installment in sorted(loan.installments, key=lambda item: item.installment_number):
        if getattr(installment, "is_superseded", False) or installment.status == InstallmentStatus.PAID:
            continue
        installment_balance = money(Decimal(installment.total_due) - Decimal(installment.paid_amount))
        allocation = min(remaining_to_simulate, installment_balance)
        if allocation >= installment_balance and installment_balance > 0:
            installments_covered += 1
        remaining_to_simulate = money(remaining_to_simulate - allocation)
        if remaining_to_simulate <= 0:
            break

    early_settlement_required, future_installments = early_settlement_required_for_payoff(
        loan,
        amount_applied=applied,
        as_of_date=payment_date,
    )

    person = loan.borrower.user.person if loan.borrower and loan.borrower.user else None
    borrower_name = (
        " ".join(
            value
            for value in [
                getattr(person, "first_name", None),
                getattr(person, "middle_name", None),
                getattr(person, "last_name", None),
            ]
            if value
        )
        or "Borrower"
    )
    return {
        "loan_id": loan.id,
        "loan_reference": loan.loan_reference,
        "borrower_name": borrower_name,
        "current_installment_number": current.installment_number,
        "current_due_date": current.due_date,
        "expected_monthly_installment": money(loan.installment_amount),
        "installment_outstanding_before": outstanding,
        "amount_tendered": tendered,
        "amount_applied": money(applied),
        "change_amount": money(change),
        "forward_amount": money(forward),
        "installment_outstanding_after": remaining_current,
        "loan_balance_before": loan_balance,
        "loan_balance_after": money(max(loan_balance - applied, Decimal("0"))),
        "installments_fully_covered": installments_covered,
        "payment_completes_loan": applied >= loan_balance,
        "early_settlement_required": early_settlement_required,
        "future_installments_in_payoff": future_installments,
    }


def _existing_payment(db: Session, idempotency_key: str | None) -> PaymentTransaction | None:
    if not idempotency_key:
        return None
    return (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.idempotency_key == idempotency_key)
        .first()
    )


def _recorded_payment_reference(
    payment_method: PaymentMethod,
    direction: PaymentDirection,
    proof_reference: str | None = None,
) -> str:
    if payment_method == PaymentMethod.CASH:
        return _cash_reference(direction)
    # Always generate a unique LoanHub posting reference. External proof numbers
    # belong in PaymentTransaction.proof_reference and are not guaranteed unique.
    prefix = "PIN" if direction == PaymentDirection.INBOUND else "POUT"
    return f"{prefix}-{payment_method.value.upper()}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def _require_signed_contract_before_disbursement(
    db: Session,
    loan: ClientCompanyLoan,
) -> LoanContract | None:
    """Apply the tenant's signed-contract rule to every loan origin.

    Marketplace/online loans do not have ``direct_application_id``.  The old
    implementation used that field as the switch for contract enforcement,
    which allowed an accepted online offer to be paid out with no agreement.
    A missing policy row uses the model's secure default: contracts are
    required.
    """
    policy = (
        db.query(OriginationPolicy)
        .filter(OriginationPolicy.company_id == loan.company_id)
        .first()
    )
    require_signed_contract = True if policy is None else bool(policy.require_signed_contract)
    if not require_signed_contract:
        return None

    contract = (
        db.query(LoanContract)
        .filter(
            LoanContract.loan_id == loan.id,
            LoanContract.company_id == loan.company_id,
        )
        .first()
    )
    if not contract:
        raise HTTPException(
            status_code=409,
            detail=(
                "Generate the loan contract and obtain both borrower and company "
                "signatures before disbursement"
            ),
        )

    missing: list[str] = []
    if not contract.borrower_signed_at:
        missing.append("borrower")
    if not contract.company_signed_at:
        missing.append("company")
    if contract.status != "signed" or missing:
        signer_text = " and ".join(missing) if missing else "required parties"
        raise HTTPException(
            status_code=409,
            detail=f"The loan contract is not fully signed; pending signature: {signer_text}",
        )
    return contract


def disburse_cash_loan(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[PaymentTransaction, CashTransaction | None]:
    if loan.status != LoanStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Only an approved, undisbursed loan is ready for disbursement")

    _require_signed_contract_before_disbursement(db, loan)

    key = _payment_idempotency_key(f"loan-disbursement:{loan.id}:{payment_method.value}", idempotency_key)
    existing = _existing_payment(db, key)
    if existing:
        return existing, existing.cash_transaction
    if payment_method == PaymentMethod.LELEFAPAYGATE:
        from services.lelefa_paygate_service import initiate_gateway_loan_disbursement

        amount = money(loan.top_up_cash_amount if loan.is_top_up else loan.principal_amount)
        return (
            initiate_gateway_loan_disbursement(
                db,
                loan=loan,
                amount=amount,
                idempotency_key=key,
                initiated_by_user_id=initiated_by_user_id,
            ),
            None,
        )
    if payment_method != PaymentMethod.CASH:
        raise HTTPException(
            status_code=422,
            detail="Direct electronic handlers were retired; use LelefaPayGate or cash",
        )

    from services.treasury_service import (
        get_or_create_settings,
        record_payment_treasury_entry,
        validate_manual_proof,
    )

    settings = get_or_create_settings(db, loan.company_id)
    validate_manual_proof(settings, payment_method, proof_reference, proof_url)
    disbursement_amount = money(loan.top_up_cash_amount if loan.is_top_up else loan.principal_amount)
    if disbursement_amount <= 0:
        raise HTTPException(status_code=409, detail="The loan does not have a positive amount to disburse")

    now = datetime.now(timezone.utc)
    reference = _recorded_payment_reference(payment_method, PaymentDirection.OUTBOUND, proof_reference)
    payment = PaymentTransaction(
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.CASH if payment_method == PaymentMethod.CASH else PaymentProvider.MANUAL,
        payment_method=payment_method,
        direction=PaymentDirection.OUTBOUND,
        purpose=PaymentPurpose.LOAN_DISBURSEMENT,
        status=PaymentStatus.SUCCEEDED,
        amount=disbursement_amount,
        currency="LSL",
        idempotency_key=key,
        provider_reference=reference,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        proof_notes=(proof_notes or notes or "").strip() or None,
        verified_by_user_id=initiated_by_user_id,
        verified_at=now,
        provider_payload={"method": payment_method.value, "notes": notes},
        completed_at=now,
    )
    db.add(payment)
    db.flush()

    cash: CashTransaction | None = None
    if payment_method == PaymentMethod.CASH:
        cash = CashTransaction(
            payment_id=payment.id,
            branch_id=loan.branch_id,
            handled_by_user_id=initiated_by_user_id,
            direction=PaymentDirection.OUTBOUND,
            cash_reference=reference,
            tendered_amount=payment.amount,
            applied_amount=payment.amount,
            change_amount=0,
            forward_amount=0,
            notes=notes,
        )
        db.add(cash)

    finalize_loan_payment(db, payment, commit=False)

    if loan.is_top_up:
        if not loan.parent_loan_id:
            raise HTTPException(status_code=409, detail="Top-up loan is missing its parent loan")
        existing_settlement = (
            db.query(LoanTopUpSettlement)
            .filter(LoanTopUpSettlement.new_loan_id == loan.id)
            .first()
        )
        if not existing_settlement:
            parent = (
                db.query(ClientCompanyLoan)
                .filter(ClientCompanyLoan.id == loan.parent_loan_id)
                .with_for_update()
                .first()
            )
            if not parent:
                raise HTTPException(status_code=409, detail="The original loan for this top-up was not found")
            if parent.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
                raise HTTPException(status_code=409, detail="The original loan is no longer eligible for top-up settlement")
            settlement_amount = money(parent.balance)
            configured_settlement = money(loan.top_up_settlement_amount)
            if abs(settlement_amount - configured_settlement) > MONEY:
                raise HTTPException(
                    status_code=409,
                    detail="The original loan balance changed after top-up approval; reassess the top-up before disbursement",
                )
            settlement = LoanTopUpSettlement(
                company_id=loan.company_id,
                borrower_id=loan.borrower_id,
                parent_loan_id=parent.id,
                new_loan_id=loan.id,
                settlement_amount=settlement_amount,
                cash_to_borrower=disbursement_amount,
                parent_balance_before=money(parent.balance),
                parent_amount_paid_before=money(parent.amount_paid),
                parent_status_before=parent.status.value if hasattr(parent.status, "value") else str(parent.status),
                status="settled",
                settled_at=now,
                settled_by_user_id=initiated_by_user_id,
                notes=f"Original loan {parent.loan_reference} settled from top-up {loan.loan_reference}",
            )
            db.add(settlement)
            parent.amount_paid = money(parent.total_repayable)
            parent.balance = money(0)
            parent.status = LoanStatus.COMPLETED

    record_payment_accounting(db, payment)
    from services.platform_finance_service import accrue_platform_transaction_charge
    from services.receipt_service import ensure_payment_receipt

    accrue_platform_transaction_charge(db, payment)
    ensure_payment_receipt(db, payment)
    record_payment_treasury_entry(
        db,
        payment,
        branch_id=loan.branch_id,
        description=f"Loan disbursement {loan.loan_reference}",
    )
    db.commit()
    db.refresh(payment)
    if cash:
        db.refresh(cash)
    return payment, cash

def record_borrower_request_fee(
    db: Session,
    *,
    request: LoanRequest,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[PaymentTransaction, CashTransaction | None]:
    """Receive the configured borrower request fee using verified evidence."""
    fee_amount = money(request.service_fee_amount or 0)
    if request.service_fee_status in {"paid", "not_required"}:
        if request.service_fee_payment_id:
            existing = db.get(PaymentTransaction, request.service_fee_payment_id)
            if existing:
                return existing, existing.cash_transaction
        raise HTTPException(status_code=409, detail="This request does not have an outstanding service fee")
    if fee_amount <= 0:
        raise HTTPException(status_code=409, detail="This request does not have a payable service fee")

    key = _payment_idempotency_key(f"borrow-request-fee:{request.id}", idempotency_key)
    existing = _existing_payment(db, key)
    if existing:
        return existing, existing.cash_transaction

    from services.payment_service import initiate_payment

    payment = initiate_payment(
        db,
        provider=PaymentProvider.CASH if payment_method == PaymentMethod.CASH else PaymentProvider.MANUAL,
        purpose=PaymentPurpose.BORROW_REQUEST_FEE,
        amount=fee_amount,
        idempotency_key=key,
        initiated_by_user_id=initiated_by_user_id,
        borrower_id=request.borrower_id,
        loan_request_id=request.id,
        payment_method=payment_method,
        proof_reference=proof_reference,
        proof_url=proof_url,
        proof_notes=proof_notes or notes,
    )
    return payment, payment.cash_transaction


def record_cash_borrower_request_fee(
    db: Session,
    *,
    request: LoanRequest,
    initiated_by_user_id: UUID,
    notes: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[PaymentTransaction, CashTransaction | None]:
    """Backward-compatible cash-only wrapper."""
    return record_borrower_request_fee(
        db,
        request=request,
        initiated_by_user_id=initiated_by_user_id,
        payment_method=PaymentMethod.CASH,
        notes=notes,
        idempotency_key=idempotency_key,
    )

def record_cash_repayment(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    amount_tendered: Decimal,
    overpayment_action: str,
    installment_number: int | None,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    gateway_provider: str | None = None,
    gateway_customer_phone: str | None = None,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
    payment_date: date | None = None,
    backdated_by_company_owner: bool = False,
) -> tuple[PaymentTransaction, CashTransaction | None, dict[str, Any]]:
    """Post a loan repayment through cash or a manually verified channel."""
    if payment_method != PaymentMethod.CASH and overpayment_action == "give_change":
        raise HTTPException(
            status_code=422,
            detail="Non-cash payments cannot produce physical change. Carry the excess forward instead.",
        )

    preview = preview_cash_repayment(
        loan,
        amount_tendered=amount_tendered,
        overpayment_action=overpayment_action,
        installment_number=installment_number,
        payment_date=payment_date,
    )
    if preview["early_settlement_required"]:
        count = preview["future_installments_in_payoff"]
        noun = "instalment" if count == 1 else "instalments"
        raise HTTPException(
            status_code=409,
            detail=(
                f"This payment would close {count} future {noun} using the original full-term interest. "
                "Create and acknowledge an early-settlement quote so unearned interest is rebated."
            ),
        )
    key = _payment_idempotency_key(f"loan-repayment:{loan.id}:{payment_method.value}", idempotency_key)
    existing = _existing_payment(db, key)
    if existing:
        return existing, existing.cash_transaction, preview

    from services.early_settlement_service import assert_no_settlement_in_progress

    assert_no_settlement_in_progress(db, loan.id)
    if payment_method == PaymentMethod.LELEFAPAYGATE:
        from services.lelefa_paygate_service import initiate_gateway_loan_repayment

        payment = initiate_gateway_loan_repayment(
            db,
            loan=loan,
            amount=preview["amount_applied"],
            idempotency_key=key,
            initiated_by_user_id=initiated_by_user_id,
            gateway_provider=gateway_provider,
            payer_phone=gateway_customer_phone,
        )
        return payment, None, preview
    if payment_method != PaymentMethod.CASH:
        raise HTTPException(
            status_code=422,
            detail="Direct electronic handlers were retired; use LelefaPayGate or cash",
        )

    from services.treasury_service import (
        get_or_create_settings,
        record_payment_treasury_entry,
        validate_manual_proof,
    )

    settings = get_or_create_settings(db, loan.company_id)
    validate_manual_proof(settings, payment_method, proof_reference, proof_url)
    now = datetime.now(timezone.utc)
    effective_at = payment_date_to_utc(payment_date) if payment_date else now
    reference = _recorded_payment_reference(payment_method, PaymentDirection.INBOUND, proof_reference)
    payment = PaymentTransaction(
        company_id=loan.company_id,
        borrower_id=loan.borrower_id,
        loan_request_id=loan.loan_request_id,
        loan_id=loan.id,
        initiated_by_user_id=initiated_by_user_id,
        provider=PaymentProvider.CASH if payment_method == PaymentMethod.CASH else PaymentProvider.MANUAL,
        payment_method=payment_method,
        direction=PaymentDirection.INBOUND,
        purpose=PaymentPurpose.LOAN_REPAYMENT,
        status=PaymentStatus.SUCCEEDED,
        amount=preview["amount_applied"],
        currency="LSL",
        idempotency_key=key,
        provider_reference=reference,
        proof_reference=(proof_reference or "").strip() or None,
        proof_url=(proof_url or "").strip() or None,
        proof_notes=(proof_notes or notes or "").strip() or None,
        verified_by_user_id=initiated_by_user_id,
        verified_at=now,
        provider_payload={
            "method": payment_method.value,
            "overpayment_action": overpayment_action,
            "amount_tendered": str(preview["amount_tendered"]),
            "change_amount": str(preview["change_amount"]),
            "forward_amount": str(preview["forward_amount"]),
            "notes": notes,
            "effective_payment_date": payment_date.isoformat() if payment_date else None,
            "backdated_by_company_owner": backdated_by_company_owner,
        },
        completed_at=effective_at,
    )
    db.add(payment)
    db.flush()

    cash: CashTransaction | None = None
    if payment_method == PaymentMethod.CASH:
        cash = CashTransaction(
            payment_id=payment.id,
            branch_id=loan.branch_id,
            handled_by_user_id=initiated_by_user_id,
            direction=PaymentDirection.INBOUND,
            cash_reference=reference,
            tendered_amount=preview["amount_tendered"],
            applied_amount=preview["amount_applied"],
            change_amount=preview["change_amount"],
            forward_amount=preview["forward_amount"],
            installment_number=preview["current_installment_number"],
            expected_installment_amount=preview["expected_monthly_installment"],
            installment_outstanding_before=preview["installment_outstanding_before"],
            installment_outstanding_after=preview["installment_outstanding_after"],
            notes=notes,
        )
        db.add(cash)

    finalize_loan_payment(db, payment, commit=False)
    record_payment_accounting(db, payment)
    from services.platform_finance_service import accrue_platform_transaction_charge
    from services.receipt_service import ensure_payment_receipt

    accrue_platform_transaction_charge(db, payment)
    ensure_payment_receipt(db, payment)
    record_payment_treasury_entry(
        db,
        payment,
        branch_id=loan.branch_id,
        description=f"Loan repayment {loan.loan_reference}",
    )
    db.commit()
    db.refresh(payment)
    if cash:
        db.refresh(cash)
    return payment, cash, preview


def record_installment_repayment(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    installment_id: UUID,
    amount_tendered: Decimal,
    initiated_by_user_id: UUID,
    payment_method: PaymentMethod = PaymentMethod.CASH,
    gateway_provider: str | None = None,
    gateway_customer_phone: str | None = None,
    proof_reference: str | None = None,
    proof_url: str | None = None,
    proof_notes: str | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
    payment_date: date | None = None,
    backdated_by_company_owner: bool = False,
) -> tuple[PaymentTransaction, CashTransaction | None, dict[str, Any]]:
    """Record a payment against the current installment only.

    The repayment-schedule row action intentionally does not carry money into
    later installments. Advance/overpayment workflows remain available through
    the payment desk.
    """
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="This loan is not accepting repayments")

    installment = next(
        (item for item in loan.installments if item.id == installment_id),
        None,
    )
    if not installment:
        raise HTTPException(status_code=404, detail="Installment not found for this loan")

    if getattr(installment, "is_superseded", False):
        raise HTTPException(
            status_code=409,
            detail="This installment was rolled into a maturity renewal cycle and is historical only",
        )
    if installment.status in {InstallmentStatus.PAID, InstallmentStatus.WAIVED}:
        raise HTTPException(
            status_code=409,
            detail="This installment is already settled and cannot receive another payment",
        )

    current = _first_open_installment(loan)
    if not current:
        raise HTTPException(status_code=409, detail="This loan has no unpaid installment")
    if current.id != installment.id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Installment {current.installment_number} must be cleared before "
                f"installment {installment.installment_number}"
            ),
        )

    tendered = money(amount_tendered)
    outstanding = money(Decimal(installment.total_due) - Decimal(installment.paid_amount))
    if tendered <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    if tendered > outstanding:
        raise HTTPException(
            status_code=422,
            detail=(
                f"This installment has {outstanding:.2f} outstanding. "
                "Use the payment desk for an advance or overpayment."
            ),
        )

    return record_cash_repayment(
        db,
        loan=loan,
        amount_tendered=tendered,
        overpayment_action="carry_forward",
        installment_number=installment.installment_number,
        initiated_by_user_id=initiated_by_user_id,
        payment_method=payment_method,
        gateway_provider=gateway_provider,
        gateway_customer_phone=gateway_customer_phone,
        proof_reference=proof_reference,
        proof_url=proof_url,
        proof_notes=proof_notes,
        notes=notes,
        idempotency_key=idempotency_key,
        payment_date=payment_date,
        backdated_by_company_owner=backdated_by_company_owner,
    )


def allocate_repayment(db: Session, payment: PaymentTransaction) -> None:
    loan = payment.loan or db.get(ClientCompanyLoan, payment.loan_id)
    if not loan:
        return

    remaining = money(payment.amount)
    installments = (
        db.query(RepaymentInstallment)
        .filter(
            RepaymentInstallment.loan_id == loan.id,
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.status.in_(
                [
                    InstallmentStatus.PENDING,
                    InstallmentStatus.PARTIALLY_PAID,
                    InstallmentStatus.OVERDUE,
                ]
            ),
        )
        .order_by(RepaymentInstallment.installment_number.asc())
        .all()
    )

    for installment in installments:
        if remaining <= 0:
            break
        outstanding = money(Decimal(installment.total_due) - Decimal(installment.paid_amount))
        allocated = min(remaining, outstanding)
        installment.paid_amount = money(Decimal(installment.paid_amount) + allocated)
        remaining = money(remaining - allocated)
        db.add(PaymentAllocation(payment_id=payment.id, installment_id=installment.id, amount=allocated))
        if Decimal(installment.paid_amount) >= Decimal(installment.total_due):
            installment.status = InstallmentStatus.PAID
            installment.paid_at = payment.completed_at or datetime.now(timezone.utc)
        else:
            installment.status = InstallmentStatus.PARTIALLY_PAID

    loan.amount_paid = money(Decimal(loan.amount_paid) + Decimal(payment.amount))
    loan.balance = money(max(Decimal(loan.total_repayable) - Decimal(loan.amount_paid), Decimal("0")))
    if loan.balance <= 0:
        loan.status = LoanStatus.COMPLETED


def finalize_loan_payment(db: Session, payment: PaymentTransaction, *, commit: bool = True) -> None:
    if payment.status != PaymentStatus.SUCCEEDED or not payment.loan_id:
        return
    if (payment.provider_payload or {}).get("early_settlement_id"):
        return
    loan = payment.loan or db.get(ClientCompanyLoan, payment.loan_id)
    if not loan:
        return

    if payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
        loan.status = LoanStatus.ACTIVE
        loan.disbursed_at = payment.completed_at or datetime.now(timezone.utc)
        loan.disbursed_by_user_id = payment.initiated_by_user_id
    elif payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
        already_allocated = (
            db.query(PaymentAllocation)
            .filter(PaymentAllocation.payment_id == payment.id)
            .first()
        )
        if not already_allocated:
            allocate_repayment(db, payment)
    if commit:
        db.commit()


def reverse_loan_payment(db: Session, payment: PaymentTransaction) -> None:
    if not payment.loan_id:
        return
    from services.early_settlement_service import reverse_early_settlement

    if reverse_early_settlement(db, payment):
        return
    loan = payment.loan or db.get(ClientCompanyLoan, payment.loan_id)
    if not loan:
        return

    if payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
        allocations = (
            db.query(PaymentAllocation)
            .filter(PaymentAllocation.payment_id == payment.id)
            .all()
        )
        allocated_installments = [
            db.get(RepaymentInstallment, allocation.installment_id)
            for allocation in allocations
        ]
        if any(installment and getattr(installment, "is_superseded", False) for installment in allocated_installments):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This repayment belongs to a schedule that has already been capitalised into a maturity renewal. "
                    "Reverse the renewal through a controlled restructuring workflow before reversing the historical payment."
                ),
            )
        for allocation in allocations:
            installment = db.get(RepaymentInstallment, allocation.installment_id)
            if not installment:
                continue
            installment.paid_amount = money(
                max(Decimal(installment.paid_amount) - Decimal(allocation.amount), Decimal("0"))
            )
            installment.paid_at = None
            if installment.paid_amount <= 0:
                installment.status = (
                    InstallmentStatus.OVERDUE
                    if installment.due_date < date.today()
                    else InstallmentStatus.PENDING
                )
            elif installment.paid_amount < installment.total_due:
                installment.status = InstallmentStatus.PARTIALLY_PAID
        loan.amount_paid = money(max(Decimal(loan.amount_paid) - Decimal(payment.amount), Decimal("0")))
        loan.balance = money(max(Decimal(loan.total_repayable) - Decimal(loan.amount_paid), Decimal("0")))
        if loan.status == LoanStatus.COMPLETED and loan.balance > 0:
            loan.status = LoanStatus.ACTIVE
    elif payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
        loan.status = LoanStatus.APPROVED
        loan.disbursed_at = None
        loan.disbursed_by_user_id = None
        if loan.is_top_up:
            settlement = (
                db.query(LoanTopUpSettlement)
                .filter(
                    LoanTopUpSettlement.new_loan_id == loan.id,
                    LoanTopUpSettlement.status == "settled",
                )
                .first()
            )
            if settlement:
                parent = db.get(ClientCompanyLoan, settlement.parent_loan_id)
                if parent:
                    parent.balance = money(settlement.parent_balance_before)
                    parent.amount_paid = money(settlement.parent_amount_paid_before)
                    try:
                        parent.status = LoanStatus(settlement.parent_status_before)
                    except ValueError:
                        parent.status = LoanStatus.ACTIVE
                settlement.status = "reversed"
                settlement.reversed_at = datetime.now(timezone.utc)
                settlement.reversed_by_user_id = payment.reversed_by_user_id
