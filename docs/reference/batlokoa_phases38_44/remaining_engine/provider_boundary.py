"""Phase 40: fail-closed provider adapter contract, no external SDK or network.

There are deliberately NO concrete adapters for real providers in this package.
A test adapter exists only to exercise offline orchestration, not to send money.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from decimal import Decimal
from .contracts import Money, TenantKey, ContractError, reference
from .transaction_integrity import VerifiedProviderResult

@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    name: str
    supports_collections: bool
    supports_payouts: bool
    supports_verified_callbacks: bool
    certified_for_live: bool = False

@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    provider: str
    event_reference: str
    operation_id: str
    outcome: str
    amount: Money
    tenant: TenantKey
    provider_reference: str
    verified_by_adapter: bool

class ProviderAdapter(Protocol):
    capabilities: ProviderCapabilities
    def verify_evidence(self, raw_bytes: bytes, headers: dict[str, str]) -> EvidenceEnvelope: ...

def accept_verified_evidence(*, adapter: ProviderAdapter, envelope: EvidenceEnvelope,
                             expected_tenant: TenantKey, expected_operation: str,
                             expected_money: Money) -> VerifiedProviderResult:
    reference(expected_operation)
    for field in (envelope.operation_id, envelope.event_reference, envelope.provider_reference):
        reference(field)
    cap = adapter.capabilities
    if not cap.supports_verified_callbacks or not envelope.verified_by_adapter:
        raise ContractError('No independently verified callback evidence')
    if envelope.provider != cap.name or envelope.tenant != expected_tenant:
        raise ContractError('Wrong provider or tenant')
    if envelope.operation_id != expected_operation or envelope.amount != expected_money:
        raise ContractError('Wrong operation or amount')
    if envelope.outcome not in {'settled','failed','reversed'}:
        raise ContractError('Unsupported provider outcome')
    return VerifiedProviderResult(envelope.tenant, envelope.operation_id, envelope.amount,
                                  envelope.provider_reference, envelope.event_reference,
                                  envelope.outcome, True)

def assert_live_provider_certified(adapter: ProviderAdapter) -> None:
    """Never infer certification from a synthetic verifier or module import."""
    if not adapter.capabilities.certified_for_live:
        raise ContractError('Provider not certified for live collections')
    if not adapter.capabilities.supports_collections or not adapter.capabilities.supports_verified_callbacks:
        raise ContractError('Provider lacks required collection controls')
