"""Read-only historical opening balance evidence review; never authorizes posting."""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from uuid import UUID
from datetime import datetime, timezone

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction

from database.models.legacy_loan_capture import LegacyLoanCapture
from database.models.origination import LoanContract


@dataclass(frozen=True)
class HistoricalOpeningReview:
    credited_at_migration: Decimal
    receipt_book_total: Decimal
    excess_for_review: Decimal
    converted_at: datetime | None = None
    independently_verified: bool = False
    can_post: bool = False


def _money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Invalid historical money")
        return amount
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValueError("Invalid historical money") from exc


def review_historical_opening(*, company_id: UUID, loan_id: UUID, capture, contract):
    """Check the stored capture and contract agree, not that paper receipts are authentic."""
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    for row in (capture, contract):
        if row.company_id != company_id or row.loan_id != loan_id:
            raise ValueError("Historical evidence scope mismatch")
    if capture.status != "posted" or capture.converted_at is None:
        raise ValueError("Historical capture not posted")
    if contract.status != "historical_record":
        raise ValueError("Historical contract required")
    terms, conversion = contract.terms_snapshot, capture.conversion_data
    if not isinstance(terms, dict) or not isinstance(conversion, dict):
        raise ValueError("Historical evidence missing")
    digest = hashlib.sha256(json.dumps(terms, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != contract.contract_hash:
        raise ValueError("Historical contract snapshot hash mismatch")
    if (terms.get("source") != "legacy_cashout_book"
        or terms.get("historical_record") is not True
        or conversion.get("conversion_type") != "historical_opening_balance"
        or conversion.get("contract_number") != contract.contract_number
        or type(conversion.get("payment_transactions_created")) is not int
        or conversion["payment_transactions_created"] != 0):
        raise ValueError("Historical conversion provenance mismatch")
    principal = _money(capture.borrowed_amount)
    total = _money(capture.total_repayable or capture.borrowed_amount)
    receipts = _money(capture.amount_paid)
    credited = min(receipts, total, principal * 2)
    excess = receipts - credited
    if principal <= 0 or total <= 0:
        raise ValueError("Invalid historical contractual amounts")
    checks = (
        (terms.get("principal_amount"), principal),
        (terms.get("total_repayable"), total),
        (terms.get("duple_morule_limit"), principal * 2),
        (terms.get("amount_paid_at_migration"), credited),
        (terms.get("receipt_book_total_paid"), receipts),
        (conversion.get("receipt_book_total_paid"), receipts),
        (terms.get("overpayment_for_reconciliation"), excess),
        (conversion.get("overpayment_for_reconciliation"), excess),
    )
    if any(_money(value) != expected for value, expected in checks):
        raise ValueError("Historical opening amounts disagree")
    return HistoricalOpeningReview(credited, receipts, excess, converted_at=capture.converted_at)


def inspect_historical_opening(db, *, company_id: UUID, loan_id: UUID):
    """Load only the requested tenant and loan; missing evidence fails closed."""
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    capture = db.query(LegacyLoanCapture).filter(
        LegacyLoanCapture.company_id == company_id, LegacyLoanCapture.loan_id == loan_id,
    ).one_or_none()
    contract = db.query(LoanContract).filter(
        LoanContract.company_id == company_id, LoanContract.loan_id == loan_id,
    ).one_or_none()
    if capture is None or contract is None:
        raise ValueError("Historical opening evidence missing")
    return review_historical_opening(company_id=company_id, loan_id=loan_id,
                                     capture=capture, contract=contract)


@dataclass(frozen=True)
class HistoricalLiveComparison:
    opening_credit: Decimal
    recorded_live_repayments: Decimal
    recorded_loan_paid: Decimal
    difference: Decimal
    unresolved_rows: int
    independently_verified: bool = False


def _utc(value):
    if not isinstance(value, datetime):
        raise ValueError("Missing payment chronology")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def compare_historical_live_payments(*, opening, recorded_paid, payments, company_id, loan_id):
    """Gross local comparison only; refunds and reversals are never silently netted."""
    cutoff = _utc(opening.converted_at)
    paid = _money(recorded_paid)
    gross = Decimal("0.00")
    unresolved = 0
    seen = set()
    for row in payments:
        if row.company_id != company_id or row.loan_id != loan_id:
            raise ValueError("Payment scope mismatch")
        if not row.id or row.id in seen:
            unresolved += 1
            continue
        seen.add(row.id)
        if row.purpose != PaymentPurpose.LOAN_REPAYMENT:
            unresolved += 1
            continue
        if row.status != PaymentStatus.SUCCEEDED or row.direction != PaymentDirection.INBOUND:
            unresolved += 1
            continue
        try:
            amount = _money(row.amount)
            if row.currency != "LSL" or amount <= 0 or _utc(row.completed_at) < cutoff:
                raise ValueError("Unresolved payment evidence")
        except (ValueError, AttributeError):
            unresolved += 1
            continue
        gross += amount
    return HistoricalLiveComparison(opening.credited_at_migration, gross, paid,
        paid - opening.credited_at_migration - gross, unresolved)


def inspect_historical_live_payments(db, *, opening, recorded_paid, company_id, loan_id):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    rows = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == loan_id,
    ).all()
    return compare_historical_live_payments(opening=opening, recorded_paid=recorded_paid,
        payments=rows, company_id=company_id, loan_id=loan_id)
