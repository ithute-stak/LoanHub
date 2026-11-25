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
    verified_reversals: Decimal
    net_collected: Decimal | None
    unresolved: tuple[str, ...]
    complete: bool = False


def _amount(value: Decimal) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            raise ValueError("Amounts must be positive finite currency values")
        # Quantization can raise InvalidOperation for very large finite
        # Decimals under the active context precision. It must fail closed
        # as evidence, not abort the settlement-readiness endpoint.
        return amount.quantize(CENT)
    except (InvalidOperation, ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid monetary amount") from exc


def preview_reconciliation(rows: Iterable[PaymentEvidence]) -> ReconciliationPreview:
    """Inspect normalized payment evidence without trusting unverified status.

    Callers must supply independently verified mappings for direction, status,
    original-payment linkage, and all legacy/manual/refund sources. This is
    not an authoritative adapter and always returns complete=False.
    """
    seen: set[str] = set()
    collections: dict[str, Decimal] = {}
    refunds: list[tuple[str, Decimal]] = []
    reversals: list[tuple[str, Decimal]] = []
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
        elif row.direction == "reversal" and row.status == "completed":
            if not row.original_payment_id:
                unresolved.append(f"{row.payment_id}:missing_original_payment")
            else:
                reversals.append((row.original_payment_id, amount))
        else:
            unresolved.append(f"{row.payment_id}:unresolved_status_or_direction")

    # Refunds and provider reversals debit the same original collection.
    # Individually valid adjustments can still collectively exceed it.
    deductions: dict[str, Decimal] = {}
    refunded_total = Decimal("0.00")
    reversed_total = Decimal("0.00")
    for kind, entries in (("refund", refunds), ("reversal", reversals)):
        for original_id, amount in entries:
            if original_id not in collections:
                unresolved.append(f"{original_id}:{kind}_without_verified_collection")
                continue
            deductions[original_id] = deductions.get(original_id, Decimal("0.00")) + amount
            if kind == "refund":
                refunded_total += amount
            else:
                reversed_total += amount
            if deductions[original_id] > collections[original_id]:
                unresolved.append(f"{original_id}:deductions_exceed_collection")

    gross = sum(collections.values(), Decimal("0.00"))
    total_refunds = refunded_total
    return ReconciliationPreview(
        gross_collected=gross,
        verified_refunds=total_refunds,
        verified_reversals=reversed_total,
        net_collected=gross - total_refunds - reversed_total if not unresolved else None,
        unresolved=tuple(unresolved),
        complete=False,
    )
