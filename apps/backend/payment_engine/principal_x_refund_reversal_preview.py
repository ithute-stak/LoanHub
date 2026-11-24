"""Fail-closed, read-only refund/reversal reconciliation for Principal x%.

This module intentionally cannot certify ledger completeness or authorize posting.
Amounts are counted once per authoritative payment id, never once per cash,
allocation or treasury row. External refund evidence must be independently
verified before a net-collected balance can be certified.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

CENT = Decimal("0.01")


@dataclass(frozen=True)
class PaymentEvidence:
    payment_id: str
    amount: Decimal
    status: str
    direction: str
    currency: str = "LSL"
    original_payment_id: str | None = None
    verified: bool = False


@dataclass(frozen=True)
class ReconciliationPreview:
    gross_collected: Decimal
    verified_refunds: Decimal
    net_collected: Decimal | None
    unresolved: tuple[str, ...]
    complete: bool = False


def _amount(value: Decimal) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid monetary amount") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError("Amounts must be positive finite currency values")
    return amount.quantize(CENT)


def preview_reconciliation(rows: Iterable[PaymentEvidence]) -> ReconciliationPreview:
    """Inspect normalized payment evidence without trusting unverified status.

    Callers must supply independently verified mappings for direction, status,
    original-payment linkage, and all legacy/manual/refund sources. This is
    not an authoritative adapter and always returns complete=False.
    """
    seen: set[str] = set()
    collections: dict[str, Decimal] = {}
    refunds: list[tuple[str, Decimal]] = []
    unresolved: list[str] = []
    for row in rows:
        if not row.payment_id or row.payment_id in seen:
            unresolved.append("missing_or_duplicate_payment_id")
            continue
        seen.add(row.payment_id)
        if row.currency != "LSL":
            unresolved.append(f"{row.payment_id}:unsupported_currency")
            continue
        try:
            amount = _amount(row.amount)
        except ValueError:
            unresolved.append(f"{row.payment_id}:invalid_amount")
            continue
        if not row.verified:
            unresolved.append(f"{row.payment_id}:unverified")
            continue
        if row.direction == "collection" and row.status == "completed":
            collections[row.payment_id] = amount
        elif row.direction == "refund" and row.status == "completed":
            if not row.original_payment_id:
                unresolved.append(f"{row.payment_id}:missing_original_payment")
            else:
                refunds.append((row.original_payment_id, amount))
        else:
            unresolved.append(f"{row.payment_id}:unresolved_status_or_direction")

    refunded: dict[str, Decimal] = {}
    for original_id, amount in refunds:
        if original_id not in collections:
            unresolved.append(f"{original_id}:refund_without_verified_collection")
            continue
        refunded[original_id] = refunded.get(original_id, Decimal("0.00")) + amount
        if refunded[original_id] > collections[original_id]:
            unresolved.append(f"{original_id}:refund_exceeds_collection")

    gross = sum(collections.values(), Decimal("0.00"))
    total_refunds = sum(refunded.values(), Decimal("0.00"))
    return ReconciliationPreview(
        gross_collected=gross,
        verified_refunds=total_refunds,
        net_collected=gross - total_refunds if not unresolved else None,
        unresolved=tuple(unresolved),
        complete=False,
    )
