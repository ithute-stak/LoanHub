"""Read-only Principal x posting gate over existing PaymentTransaction rows.

This is deliberately NOT a posting service. Historical REVERSED payments,
refunds and provider-specific adjustments cannot be inferred reliably from
PaymentTransaction alone. Block rather than silently undercount collections.
The caller must own a loan-level database lock and a verified provider result.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_collection_ceiling import (
    CollectionCeiling, require_collection_within_ceiling,
)


@dataclass(frozen=True)
class PostingSnapshot:
    company_id: UUID
    loan_id: UUID
    original_principal: Decimal
    transactions: tuple
    reconciled_adjustments: bool = False


def assess_principal_x_posting(
    *, snapshot: PostingSnapshot, proposed_amount: Decimal,
    idempotency_key: str, provider_confirmed: bool,
    lock_held: bool, live_policy_enabled: bool,
) -> CollectionCeiling:
    """Reject unsafe payment snapshots; never writes or claims atomicity.

    Caller must obtain and hold a database row lock and use a durable unique
    idempotency key inside the same transaction as the eventual payment write.
    """
    if not (lock_held and provider_confirmed and live_policy_enabled):
        raise ValueError("Loan lock, provider confirmation and live policy required")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key required")
    if not isinstance(snapshot.company_id, UUID) or not isinstance(snapshot.loan_id, UUID):
        raise ValueError("Verified company and loan required")
    if not snapshot.reconciled_adjustments:
        raise ValueError("Authoritative refund/reversal reconciliation required")

    # This strict adapter accepts only final, inbound loan repayments. Any
    # non-final or adjusted transaction requires a richer ledger snapshot.
    from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus

    total = Decimal("0.00")
    seen = set()
    for tx in snapshot.transactions:
        if tx.company_id != snapshot.company_id or tx.loan_id != snapshot.loan_id:
            raise ValueError("Cross-company or cross-loan payment snapshot")
        key = tx.idempotency_key
        if not key or key in seen:
            raise ValueError("Missing or duplicate historical idempotency key")
        if key == idempotency_key:
            raise ValueError("Existing idempotency key; resolve original transaction")
        seen.add(key)
        if tx.direction != PaymentDirection.INBOUND or tx.purpose != PaymentPurpose.LOAN_REPAYMENT:
            raise ValueError("Unexpected payment direction or purpose")
        if tx.status != PaymentStatus.SUCCEEDED:
            raise ValueError("Non-final or reversed payment requires authoritative reconciliation")
        amount = Decimal(str(tx.amount))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Invalid historical collection amount")
        total += amount
    return require_collection_within_ceiling(
        original_principal=snapshot.original_principal,
        net_collected=total,
        proposed_collection=proposed_amount,
    )
