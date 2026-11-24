"""Fail-closed Principal x settlement offer and acceptance policy.

Pure domain functions: no signatures, payment posting, network or DB writes.
A quote is informational until a separate verified borrower acceptance is
persisted and the authoritative ledger is rechecked under a loan lock.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_settlement import PrincipalXQuote


@dataclass(frozen=True)
class SettlementOffer:
    loan_id: UUID
    company_id: UUID
    quote: PrincipalXQuote
    issued_at: datetime
    expires_at: datetime
    ledger_revision: str
    currency: str = "LSL"


@dataclass(frozen=True)
class BorrowerAcceptance:
    loan_id: UUID
    company_id: UUID
    accepted_amount: Decimal
    accepted_at: datetime
    ledger_revision: str
    verified_identity: bool
    consent_evidence_id: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


def issue_settlement_offer(
    *, loan_id: UUID, company_id: UUID, quote: PrincipalXQuote,
    issued_at: datetime, expires_at: datetime, ledger_revision: str,
) -> SettlementOffer:
    if not isinstance(loan_id, UUID) or not isinstance(company_id, UUID):
        raise ValueError("Verified loan and company UUIDs required")
    if not ledger_revision or not ledger_revision.strip():
        raise ValueError("Authoritative ledger revision required")
    issued = _utc(issued_at)
    expiry = _utc(expires_at)
    if expiry <= issued:
        raise ValueError("Quote expiry must be after issuance")
    if not isinstance(quote, PrincipalXQuote):
        raise ValueError("Principal x quote required")
    amount = quote.collectible_due
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValueError("No positive collectible settlement balance")
    if amount > quote.lifetime_cap_remaining or amount > quote.uncapped_due:
        raise ValueError("Quote violates settlement ceiling")
    return SettlementOffer(
        loan_id=loan_id, company_id=company_id, quote=quote,
        issued_at=issued, expires_at=expiry,
        ledger_revision=ledger_revision.strip(),
    )


def validate_settlement_acceptance(
    *, offer: SettlementOffer, acceptance: BorrowerAcceptance,
    current_ledger_revision: str, now: datetime,
) -> None:
    """Validate intent only; never authorize a collection by itself.

    Caller must additionally verify evidence authenticity, authorization,
    company/loan ownership, transaction idempotency, current loan balance,
    cumulative collections, and concurrency under the posting lock.
    """
    current = _utc(now)
    accepted = _utc(acceptance.accepted_at)
    if current > offer.expires_at or accepted > offer.expires_at:
        raise ValueError("Settlement quote expired")
    if accepted < offer.issued_at or accepted > current:
        raise ValueError("Acceptance timestamp outside valid window")
    if acceptance.loan_id != offer.loan_id or acceptance.company_id != offer.company_id:
        raise ValueError("Settlement identity mismatch")
    if not acceptance.verified_identity or not acceptance.consent_evidence_id.strip():
        raise ValueError("Verified borrower consent evidence required")
    if (not current_ledger_revision
        or current_ledger_revision != offer.ledger_revision
        or acceptance.ledger_revision != offer.ledger_revision):
        raise ValueError("Ledger changed; fresh quote and consent required")
    amount = acceptance.accepted_amount
    if (not isinstance(amount, Decimal) or not amount.is_finite()
        or amount != offer.quote.collectible_due):
        raise ValueError("Accepted amount differs from settlement quote")
