"""Pure non-posting settlement matching and exception classification."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from financial_allocation import cents

class MatchStatus(str, Enum):
    MATCHED = "matched"
    MISSING_INTERNAL = "missing_internal"
    MISSING_PROVIDER = "missing_provider"
    AMOUNT_MISMATCH = "amount_mismatch"
    DUPLICATE_PROVIDER = "duplicate_provider"
    DUPLICATE_INTERNAL = "duplicate_internal"
    CURRENCY_MISMATCH = "currency_mismatch"

@dataclass(frozen=True)
class PaymentRecord:
    reference: str
    amount: Decimal
    currency: str = "LSL"

@dataclass(frozen=True)
class ReconciliationItem:
    reference: str
    status: MatchStatus
    internal_amount: Decimal | None
    provider_amount: Decimal | None

def reconcile(*, internal: tuple[PaymentRecord, ...],
              provider: tuple[PaymentRecord, ...]) -> tuple[ReconciliationItem, ...]:
    for record in (*internal, *provider):
        if not isinstance(record.reference, str) or not record.reference:
            raise ValueError("Invalid reference")
        cents(record.amount)
        if record.amount <= 0:
            raise ValueError("Nonpositive reconciliation amount")
    by_internal: dict[str, list[PaymentRecord]] = {}
    by_provider: dict[str, list[PaymentRecord]] = {}
    for record in internal:
        by_internal.setdefault(record.reference, []).append(record)
    for record in provider:
        by_provider.setdefault(record.reference, []).append(record)
    results = []
    for ref in sorted(set(by_internal) | set(by_provider)):
        left, right = by_internal.get(ref, []), by_provider.get(ref, [])
        la = left[0].amount if len(left) == 1 else None
        ra = right[0].amount if len(right) == 1 else None
        if len(left) > 1:
            status = MatchStatus.DUPLICATE_INTERNAL
        elif len(right) > 1:
            status = MatchStatus.DUPLICATE_PROVIDER
        elif not left:
            status = MatchStatus.MISSING_INTERNAL
        elif not right:
            status = MatchStatus.MISSING_PROVIDER
        elif left[0].currency != right[0].currency or left[0].currency != "LSL":
            status = MatchStatus.CURRENCY_MISMATCH
        elif la != ra:
            status = MatchStatus.AMOUNT_MISMATCH
        else:
            status = MatchStatus.MATCHED
        results.append(ReconciliationItem(ref, status, la, ra))
    return tuple(results)
