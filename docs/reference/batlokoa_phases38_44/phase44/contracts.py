"""Strict boundary types for a synthetic non-executing collection pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re
from uuid import UUID

CENT = Decimal('0.01')
KEY_RE = re.compile(r'[A-Za-z0-9_-]{16,128}\Z')
REF_RE = re.compile(r'[A-Za-z0-9_-]{8,128}\Z')
HASH_RE = re.compile(r'[0-9a-f]{64}\Z')


class BoundaryError(ValueError):
    pass


def money(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise BoundaryError('Finite Decimal required')
    if value <= 0 or value > Decimal('9999999999999999.99') or value != value.quantize(CENT):
        raise BoundaryError('Invalid positive LSL cents')
    return format(value, '.2f')


def opaque(value: str, pattern=REF_RE) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise BoundaryError('Invalid opaque identifier')
    return value


def uuid(value: UUID) -> str:
    if not isinstance(value, UUID):
        raise BoundaryError('UUID required')
    return str(value)


@dataclass(frozen=True, slots=True)
class Collection:
    company_id: UUID
    loan_id: UUID
    borrower_id: UUID
    operation_id: str
    idempotency_key: str
    amount: Decimal
    policy_version: str

    def __post_init__(self):
        for field in ('company_id', 'loan_id', 'borrower_id'):
            uuid(getattr(self, field))
        opaque(self.operation_id)
        opaque(self.idempotency_key, KEY_RE)
        opaque(self.policy_version)
        money(self.amount)

    @property
    def fingerprint(self):
        payload = {'v': 1, 'company': uuid(self.company_id), 'loan': uuid(self.loan_id),
                   'borrower': uuid(self.borrower_id), 'operation': self.operation_id,
                   'amount': money(self.amount), 'currency': 'LSL',
                   'policy_version': self.policy_version}
        return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderAttestation:
    """Issued only after real adapter verification; this module cannot create one from HTTP."""
    company_id: UUID
    operation_id: str
    provider_id: str
    event_id: str
    provider_reference: str
    amount: Decimal
    outcome: str
    payload_digest: str
    authenticated: bool

    def __post_init__(self):
        uuid(self.company_id)
        for v in (self.operation_id, self.provider_id, self.event_id, self.provider_reference):
            opaque(v)
        money(self.amount)
        if self.outcome not in ('settled', 'failed', 'reversed'):
            raise BoundaryError('Unsupported outcome')
        if not isinstance(self.payload_digest, str) or not HASH_RE.fullmatch(self.payload_digest):
            raise BoundaryError('Invalid verified payload digest')
        if self.authenticated is not True:
            raise BoundaryError('Verified provider authentication required')


@dataclass(frozen=True, slots=True)
class MandateAttestation:
    company_id: UUID
    operation_id: str
    mandate_id: str
    amount_limit: Decimal
    verified: bool

    def __post_init__(self):
        uuid(self.company_id)
        opaque(self.operation_id)
        opaque(self.mandate_id)
        money(self.amount_limit)
        if self.verified is not True:
            raise BoundaryError('Independently verified mandate required')
