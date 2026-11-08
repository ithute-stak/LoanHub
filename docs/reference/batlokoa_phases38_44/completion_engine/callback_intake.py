"""Authenticated event acceptance, replay classification and size limits.

Adapters MUST validate actual provider credentials using the provider's
documented mechanism. Never call this with a fabricated verified event.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Protocol
from uuid import UUID
from remaining_engine.contracts import TenantKey, Money, ContractError, reference, fingerprint

@dataclass(frozen=True, slots=True)
class AuthenticatedCallback:
    provider: str
    event_id: str
    provider_tx_id: str
    operation_id: str
    tenant: TenantKey
    money: Money
    outcome: str
    received_at: datetime
    raw_digest: str
    authenticated: bool

class ProviderVerifier(Protocol):
    def verify(self, raw: bytes, headers: dict[str,str], received_at: datetime) -> AuthenticatedCallback: ...

def verify_callback(*, verifier: ProviderVerifier, raw: bytes,
                    headers: dict[str,str], received_at: datetime,
                    expected_provider: str, max_bytes: int=65536) -> AuthenticatedCallback:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= max_bytes:
        raise ContractError('Callback body missing or too large')
    if received_at.tzinfo is None:
        raise ContractError('Timezone-aware receipt required')
    result = verifier.verify(raw, headers, received_at)
    if not isinstance(result, AuthenticatedCallback) or not result.authenticated:
        raise ContractError('Provider-specific authentication failed')
    if result.provider != expected_provider or result.received_at != received_at:
        raise ContractError('Callback provider/receipt mismatch')
    for field in (result.event_id, result.provider_tx_id, result.operation_id):
        reference(field)
    fingerprint(result.raw_digest)
    if result.raw_digest != sha256(raw).hexdigest():
        raise ContractError('Authenticated callback hash mismatch')
    if result.outcome not in {'settled','failed','reversed'}:
        raise ContractError('Unsupported callback outcome')
    if not isinstance(result.tenant, TenantKey) or not isinstance(result.money, Money):
        raise ContractError('Unscoped provider outcome')
    return result

def deduplicate_callback(known_digest: str | None, received_digest: str) -> str:
    fingerprint(received_digest)
    if known_digest is None:
        return 'new'
    fingerprint(known_digest)
    return 'replay' if known_digest == received_digest else 'conflict'
