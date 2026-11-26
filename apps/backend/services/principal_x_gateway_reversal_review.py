"""Review stored gateway reversal evidence without certifying provider finality."""
from dataclasses import dataclass
from decimal import Decimal
import re
from uuid import UUID

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentProvider, PaymentStatus
from database.models.lelefa_paygate import LelefaPayGateWebhookEvent
from database.models.payment import PaymentTransaction


@dataclass(frozen=True)
class GatewayReversalReview:
    reversed_payment_count: int
    corroborated_payment_count: int
    missing_evidence_count: int
    inconsistent_event_count: int
    complete: bool = False


def _money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid gateway amount")
    return amount


def review_gateway_reversals(*, company_id: UUID, loan_id: UUID, payments, events):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    indexed = {}
    for row in payments:
        if row.company_id != company_id or row.loan_id != loan_id or row.id in indexed:
            raise ValueError("Invalid payment scope or identity")
        indexed[row.id] = row
    candidates = {key: row for key, row in indexed.items()
        if row.provider == PaymentProvider.LELEFAPAYGATE
        and row.status == PaymentStatus.REVERSED
        and row.purpose == PaymentPurpose.LOAN_REPAYMENT
        and row.direction == PaymentDirection.INBOUND}
    corroborated = set()
    seen = set()
    inconsistent = 0
    for event in events:
        if event.payment_id not in indexed:
            raise ValueError("Webhook scope mismatch")
        if event.payment_id not in candidates:
            continue
        if str(event.event_type).rsplit(".", 1)[-1] != "reversed":
            continue
        payment = candidates[event.payment_id]
        payload = event.payload
        data = payload.get("data") if isinstance(payload, dict) else None
        metadata = data.get("metadata") if isinstance(data, dict) else None
        try:
            if (
                not isinstance(event.event_id, str) or not event.event_id.strip()
                or event.event_id in seen or event.processing_status != "processed"
                or event.processed_at is None or event.processing_error
                or not isinstance(event.payload_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", event.payload_hash)
                or not isinstance(data, dict) or payload.get("type") != event.event_type
                or not payment.provider_reference
                or str(data.get("id") or "") != payment.provider_reference
                or (isinstance(metadata, dict) and metadata.get("loanhub_payment_id") is not None
                    and str(metadata["loanhub_payment_id"]) != str(payment.id))
                or data.get("currency") != "LSL" or payment.currency != "LSL"
                or _money(data.get("amount")) != _money(payment.amount)
            ):
                raise ValueError("Incomplete gateway evidence")
        except (ValueError, TypeError, ArithmeticError):
            inconsistent += 1
            continue
        seen.add(event.event_id)
        corroborated.add(payment.id)
    return GatewayReversalReview(len(candidates), len(corroborated),
        len(candidates) - len(corroborated), inconsistent)


def inspect_gateway_reversals(db, *, company_id: UUID, loan_id: UUID):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == loan_id,
    ).all()
    events = db.query(LelefaPayGateWebhookEvent).join(
        PaymentTransaction, LelefaPayGateWebhookEvent.payment_id == PaymentTransaction.id,
    ).filter(PaymentTransaction.company_id == company_id,
             PaymentTransaction.loan_id == loan_id).all()
    return review_gateway_reversals(company_id=company_id, loan_id=loan_id,
                                    payments=payments, events=events)
