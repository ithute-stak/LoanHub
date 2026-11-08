"""Accepts ONLY previously verified external provider evidence; no DIY live signatures."""
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import re, hmac
from uuid import UUID

class EvidenceBindingError(ValueError):
    pass

@dataclass(frozen=True,slots=True)
class ProviderEvidence:
    provider_id: str
    provider_event_id: str
    operation_id: str
    company_id: UUID
    amount: Decimal
    currency: str
    event_kind: str
    received_at: datetime
    external_verification_id: str
    raw_body_sha256: str
    provider_status: str

@dataclass(frozen=True,slots=True)
class ExpectedOperation:
    company_id: UUID
    operation_id: str
    amount: Decimal
    currency: str
    selected_provider_id: str

def bind_verified_evidence(evidence: ProviderEvidence, expected: ExpectedOperation,
                           *, verified_provider_id: str, verified_event_id: str) -> str:
    """A provider-specific, certified verifier must run BEFORE this function.

    Evidence values cannot be sourced from unsigned user input. The separate
    verified_* values must be supplied from the trusted verifier result.
    """
    if not isinstance(evidence,ProviderEvidence) or not isinstance(expected,ExpectedOperation):
        raise EvidenceBindingError('Typed verified evidence required')
    if evidence.provider_id not in {'vodacom_mpesa_direct','econet_ecocash','golink_optional'}:
        raise EvidenceBindingError('Unknown provider')
    if not isinstance(verified_provider_id,str) or not hmac.compare_digest(evidence.provider_id,verified_provider_id):
        raise EvidenceBindingError('Provider verification mismatch')
    if not isinstance(verified_event_id,str) or not hmac.compare_digest(evidence.provider_event_id,verified_event_id):
        raise EvidenceBindingError('Unverified event identity')
    if evidence.provider_id != expected.selected_provider_id or evidence.company_id != expected.company_id:
        raise EvidenceBindingError('Provider/tenant mismatch')
    if evidence.operation_id != expected.operation_id or evidence.currency != expected.currency or evidence.currency != 'LSL':
        raise EvidenceBindingError('Operation/currency mismatch')
    if not isinstance(evidence.amount,Decimal) or evidence.amount != expected.amount or not evidence.amount.is_finite():
        raise EvidenceBindingError('Provider amount mismatch')
    if evidence.amount <= 0 or evidence.amount.as_tuple().exponent < -2:
        raise EvidenceBindingError('Invalid financial amount')
    if evidence.event_kind not in {'settled','failed','reversed'}:
        raise EvidenceBindingError('Unknown lifecycle event')
    if evidence.event_kind == 'settled' and evidence.provider_status != 'confirmed':
        raise EvidenceBindingError('Settlement not confirmed')
    if not isinstance(evidence.received_at,datetime) or evidence.received_at.tzinfo is None:
        raise EvidenceBindingError('Evidence timestamp required')
    if not isinstance(evidence.external_verification_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',evidence.external_verification_id):
        raise EvidenceBindingError('Missing independent verifier evidence')
    if not isinstance(evidence.raw_body_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',evidence.raw_body_sha256):
        raise EvidenceBindingError('Invalid raw payload hash')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',evidence.provider_event_id):
        raise EvidenceBindingError('Invalid provider event reference')
    return f'{evidence.provider_id}:{evidence.provider_event_id}'
