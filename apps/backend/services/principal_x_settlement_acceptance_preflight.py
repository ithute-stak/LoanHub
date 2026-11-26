"""Read-only Principal x% consent and stale-quote preflight.

This is a pure service boundary. Passing it does not certify borrower
identity, authenticate consent evidence, reconcile every financial source,
obtain a database lock, or authorize a payment.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_settlement_consent import (
    BorrowerAcceptance,
    SettlementOffer,
    validate_settlement_acceptance,
)
from services.principal_x_settlement_preview_service import (
    PrincipalXSnapshotQuote,
    require_unchanged_preview_snapshot,
)


@dataclass(frozen=True)
class PrincipalXAcceptancePreflight:
    loan_id: UUID
    company_id: UUID
    accepted_amount: Decimal
    snapshot_revision: str
    payment_authorized: bool = False


def preflight_principal_x_settlement_acceptance(
    *,
    offer: SettlementOffer,
    acceptance: BorrowerAcceptance,
    quoted_snapshot_revision: str,
    current_snapshot: PrincipalXSnapshotQuote,
    authoritative_ledger_revision: str,
    now: datetime,
) -> PrincipalXAcceptancePreflight:
    """Validate matching quote, consent claims and current revision, no writes.

    The authoritative ledger revision must come from a trusted locked ledger
    source. The advisory snapshot hash is NOT interchangeable with it.
    A production adapter must independently verify the borrower evidence.
    """
    require_unchanged_preview_snapshot(
        expected_revision=quoted_snapshot_revision,
        current=current_snapshot,
    )
    if current_snapshot.quote != offer.quote:
        raise ValueError("Settlement quote amount or components changed; fresh consent required")
    validate_settlement_acceptance(
        offer=offer,
        acceptance=acceptance,
        current_ledger_revision=authoritative_ledger_revision,
        now=now,
    )
    return PrincipalXAcceptancePreflight(
        loan_id=offer.loan_id,
        company_id=offer.company_id,
        accepted_amount=acceptance.accepted_amount,
        snapshot_revision=current_snapshot.snapshot_revision,
        payment_authorized=False,
    )
