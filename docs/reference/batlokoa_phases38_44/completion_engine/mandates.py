"""Fail-closed immutable lending mandate and approval contracts.

Real evidence must come from separately approved identity and consent
systems. An asserted approval boolean alone is never acceptable for live
payment operations.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from remaining_engine.contracts import TenantKey, Money, ContractError, reference

@dataclass(frozen=True, slots=True)
class Mandate:
    mandate_id: str
    tenant: TenantKey
    max_amount: Money
    issued_at: datetime
    expires_at: datetime
    consent_proof_digest: str
    independent_verifier: str
    revoked: bool = False

@dataclass(frozen=True, slots=True)
class MandateApproval:
    mandate_id: str
    operation_id: str
    approved_amount: Money
    independently_verified: bool
    evidence_digest: str

def validate_mandate(mandate: Mandate, approval: MandateApproval,
                     *, tenant: TenantKey, operation_id: str,
                     requested: Money, at: datetime) -> None:
    from remaining_engine.contracts import fingerprint
    reference(operation_id)
    reference(mandate.mandate_id)
    reference(approval.mandate_id)
    reference(mandate.independent_verifier)
    fingerprint(mandate.consent_proof_digest)
    fingerprint(approval.evidence_digest)
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ContractError('Time must be timezone aware')
    if mandate.issued_at.tzinfo is None or mandate.expires_at.tzinfo is None:
        raise ContractError('Untrusted naive mandate timestamp')
    if not mandate.issued_at < mandate.expires_at:
        raise ContractError('Invalid mandate interval')
    if not mandate.issued_at <= at < mandate.expires_at or mandate.revoked:
        raise ContractError('Mandate expired, not effective or revoked')
    if mandate.tenant != tenant or approval.mandate_id != mandate.mandate_id:
        raise ContractError('Cross-borrower or wrong mandate')
    if approval.operation_id != operation_id or approval.approved_amount != requested:
        raise ContractError('Operation or consent amount mismatch')
    if not approval.independently_verified or requested.currency != mandate.max_amount.currency:
        raise ContractError('Independent authenticated consent evidence required')
    if requested.value > mandate.max_amount.value:
        raise ContractError('Approved mandate amount exceeded')
