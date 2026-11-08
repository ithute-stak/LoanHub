"""Fail-closed operational gate; never equates a preview to payment authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
import re

class GuardError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class OperationIntent:
    company_id: UUID
    loan_id: UUID
    borrower_id: UUID
    operation_id: str
    amount: Decimal
    created_at: datetime
    mandate_company_id: UUID
    mandate_loan_id: UUID
    mandate_borrower_id: UUID
    mandate_maximum: Decimal
    mandate_expires_at: datetime
    mandate_revoked: bool
    consent_evidence_hash: str
    policy_id: str
    preview_only: bool = False

def validate_intent(intent: OperationIntent, *, trusted_company_id: UUID, now: datetime) -> None:
    if not isinstance(intent, OperationIntent):
        raise GuardError('Typed operation required')
    if not all(isinstance(x, UUID) for x in (trusted_company_id,intent.company_id,intent.loan_id,
             intent.borrower_id,intent.mandate_company_id,intent.mandate_loan_id,intent.mandate_borrower_id)):
        raise GuardError('Trusted UUID identifiers required')
    if intent.company_id != trusted_company_id or (intent.company_id,intent.loan_id,intent.borrower_id) != (
       intent.mandate_company_id,intent.mandate_loan_id,intent.mandate_borrower_id):
        raise GuardError('Mandate/company/loan scope mismatch')
    if intent.preview_only or intent.mandate_revoked:
        raise GuardError('Preview or revoked mandate cannot authorize execution')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',intent.operation_id):
        raise GuardError('Invalid opaque operation reference')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{4,128}',intent.policy_id):
        raise GuardError('Missing approved pricing/allocation policy reference')
    if not re.fullmatch(r'[0-9a-f]{64}',intent.consent_evidence_hash):
        raise GuardError('Invalid consent evidence fingerprint')
    if any(x.tzinfo is None or x.utcoffset() is None for x in (
       now,intent.created_at,intent.mandate_expires_at)):
        raise GuardError('Timezone-aware instants required')
    if not intent.created_at <= now < intent.mandate_expires_at:
        raise GuardError('Mandate not effective')
    for amt in (intent.amount,intent.mandate_maximum):
        if not isinstance(amt,Decimal) or not amt.is_finite() or amt <= 0 or amt.as_tuple().exponent < -2:
            raise GuardError('Positive finite exact cents required')
        if amt > Decimal('9999999999999999.99'):
            raise GuardError('Amount outside supported precision')
    if intent.amount > intent.mandate_maximum:
        raise GuardError('Mandate amount limit exceeded')

@dataclass(frozen=True, slots=True)
class ExecutionGate:
    provider_sandbox_certified: bool
    production_authorized: bool
    contractual_fees_approved: bool
    database_migration_approved: bool
    reconciliation_enabled: bool
    financial_posting_enabled: bool

def assert_live_release_gate(gate: ExecutionGate) -> None:
    """Fails closed by default. Requires external written approval, not this function alone."""
    if not isinstance(gate,ExecutionGate) or not all(getattr(gate,name) is True for name in gate.__dataclass_fields__):
        raise GuardError('Live financial activation not approved')
