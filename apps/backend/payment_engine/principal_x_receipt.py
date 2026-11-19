"""Immutable Principal x payment receipt projection from verified ledger events.

Pure formatting-independent receipt data, not PDF issuance. Only final,
authoritative collection events should be supplied by the calling service.
Never mark a payment as settled merely because a quote was accepted.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_collection_ceiling import money
from payment_engine.principal_x_ledger_reconciliation import (
    LedgerEvent, LedgerEventKind, reconcile_principal_x_ledger,
)


@dataclass(frozen=True)
class PrincipalXReceipt:
    receipt_reference: str
    company_id: UUID
    loan_id: UUID
    collection_event_id: str
    collected_at: datetime
    amount_received: Decimal
    currency: str
    cumulative_net_collected: Decimal
    lifetime_collection_limit: Decimal
    lifetime_allowance_remaining: Decimal
    settlement_confirmed: bool


def build_principal_x_receipt(
    *, receipt_reference: str, company_id: UUID, loan_id: UUID,
    collection_event_id: str, collected_at: datetime,
    original_principal: Decimal, events: tuple[LedgerEvent, ...],
    settlement_confirmed: bool = False, currency: str = "LSL",
) -> PrincipalXReceipt:
    """Project receipt after a confirmed ledger write; no database mutation.

    A caller must independently establish provider finality, unique receipt
    numbering, borrower identity and settlement closure before rendering.
    """
    if not receipt_reference or not receipt_reference.strip():
        raise ValueError("Receipt reference required")
    if not isinstance(collected_at, datetime) or collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("Timezone-aware collection timestamp required")
    if currency != "LSL":
        raise ValueError("Unexpected receipt currency")
    if not isinstance(settlement_confirmed, bool):
        raise ValueError("Settlement confirmation must be explicit")
    matching = [e for e in events if e.event_id == collection_event_id]
    if len(matching) != 1 or matching[0].kind is not LedgerEventKind.COLLECTION:
        raise ValueError("Receipt must reference exactly one successful collection")
    if matching[0].company_id != company_id or matching[0].loan_id != loan_id:
        raise ValueError("Receipt collection does not belong to loan/company")
    ledger = reconcile_principal_x_ledger(company_id=company_id, loan_id=loan_id, events=events)
    principal = money(original_principal)
    if principal <= 0:
        raise ValueError("Original principal must be positive")
    maximum = money(principal * Decimal("2"))
    if ledger.net_collected > maximum:
        raise ValueError("Ledger exceeds Principal x lifetime ceiling")
    return PrincipalXReceipt(
        receipt_reference=receipt_reference.strip(),
        company_id=company_id, loan_id=loan_id,
        collection_event_id=collection_event_id,
        collected_at=collected_at.astimezone(timezone.utc),
        amount_received=money(matching[0].amount), currency=currency,
        cumulative_net_collected=ledger.net_collected,
        lifetime_collection_limit=maximum,
        lifetime_allowance_remaining=money(maximum - ledger.net_collected),
        settlement_confirmed=settlement_confirmed,
    )
