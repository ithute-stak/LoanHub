"""Pure Principal x ledger reconciliation and posting preflight.

Not a posting endpoint. Production callers must load the authoritative,
loan-scoped ledger under a transaction lock, verify provider settlement and
refund evidence, enforce a unique persisted idempotency key, and commit the
result atomically. This module cannot provide those guarantees by itself.
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Sequence
from uuid import UUID

from payment_engine.principal_x_collection_ceiling import (
    money, require_collection_within_ceiling,
)


class LedgerEventKind(str, Enum):
    COLLECTION = "collection"
    REVERSAL = "reversal"
    REFUND = "refund"


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    company_id: UUID
    loan_id: UUID
    kind: LedgerEventKind
    amount: Decimal
    # A reversal/refund references the original collection, never another refund.
    original_collection_id: str | None = None


@dataclass(frozen=True)
class ReconciledLedger:
    net_collected: Decimal
    gross_collected: Decimal
    total_reversed_or_refunded: Decimal
    event_count: int


def reconcile_principal_x_ledger(
    *, company_id: UUID, loan_id: UUID, events: Sequence[LedgerEvent],
) -> ReconciledLedger:
    """Fail closed on duplicate, cross-tenant, orphan or excessive reversals.

    Event order does not affect results: references are resolved against the
    full input snapshot. Only verified, final transactions belong in events.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Company and loan UUIDs required")
    by_id: dict[str, LedgerEvent] = {}
    collections: dict[str, Decimal] = {}
    offsets: dict[str, Decimal] = {}
    gross = Decimal("0.00")
    reversed_total = Decimal("0.00")
    for event in events:
        if event.company_id != company_id or event.loan_id != loan_id:
            raise ValueError("Cross-tenant or cross-loan ledger event")
        if not isinstance(event.event_id, str) or not event.event_id.strip():
            raise ValueError("Ledger event ID required")
        if event.event_id in by_id:
            raise ValueError("Duplicate ledger event ID")
        if not isinstance(event.kind, LedgerEventKind):
            raise ValueError("Unknown ledger event kind")
        amount = money(event.amount)
        if amount <= 0:
            raise ValueError("Ledger event amount must be positive")
        by_id[event.event_id] = event
        if event.kind is LedgerEventKind.COLLECTION:
            if event.original_collection_id is not None:
                raise ValueError("Collection cannot reference another collection")
            collections[event.event_id] = amount
            gross += amount
        else:
            if not event.original_collection_id:
                raise ValueError("Refund or reversal requires original collection ID")
            offsets[event.original_collection_id] = money(
                offsets.get(event.original_collection_id, Decimal("0.00")) + amount
            )
            reversed_total += amount
    for collection_id, amount in offsets.items():
        if collection_id not in collections:
            raise ValueError("Refund or reversal references missing collection")
        if amount > collections[collection_id]:
            raise ValueError("Refunds and reversals exceed original collection")
    net = money(gross - reversed_total)
    if net < 0:
        raise ValueError("Negative net collections")
    return ReconciledLedger(
        net_collected=net,
        gross_collected=money(gross),
        total_reversed_or_refunded=money(reversed_total),
        event_count=len(by_id),
    )


def preflight_principal_x_collection(
    *, company_id: UUID, loan_id: UUID, original_principal: Decimal,
    events: Sequence[LedgerEvent], proposed_collection: Decimal,
    proposed_event_id: str,
) -> ReconciledLedger:
    """Read-only idempotency and lifetime ceiling preflight.

    The same key is always rejected here, including an apparent retry.
    An authoritative posting service must resolve retry outcomes safely.
    """
    if not isinstance(proposed_event_id, str) or not proposed_event_id.strip():
        raise ValueError("Proposed idempotency key required")
    reconciled = reconcile_principal_x_ledger(
        company_id=company_id, loan_id=loan_id, events=events,
    )
    if any(event.event_id == proposed_event_id for event in events):
        raise ValueError("Duplicate idempotency key; inspect original outcome")
    require_collection_within_ceiling(
        original_principal=original_principal,
        net_collected=reconciled.net_collected,
        proposed_collection=proposed_collection,
    )
    return reconciled
