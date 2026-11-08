"""Phase 40 deterministic reconciliation and exception queue proposals."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from .contracts import Money, TenantKey, ContractError, reference

class Decision(str, Enum):
    MATCHED = 'matched'
    MISSING_INTERNAL = 'missing_internal'
    MISSING_PROVIDER = 'missing_provider'
    DUPLICATE_INTERNAL = 'duplicate_internal'
    DUPLICATE_PROVIDER = 'duplicate_provider'
    AMOUNT_MISMATCH = 'amount_mismatch'
    TENANT_MISMATCH = 'tenant_mismatch'
    PROVIDER_MISMATCH = 'provider_mismatch'
    UNKNOWN_OUTCOME = 'unknown_outcome'
    CURRENCY_MISMATCH = 'currency_mismatch'

@dataclass(frozen=True, slots=True)
class Record:
    tenant: TenantKey
    operation_id: str
    provider_reference: str
    money: Money
    provider: str
    status: str

@dataclass(frozen=True, slots=True)
class Finding:
    operation_id: str
    decision: Decision
    requires_manual_review: bool


def reconcile(internal: tuple[Record, ...], external: tuple[Record, ...]) -> tuple[Finding, ...]:
    grouped_internal: dict[str,list[Record]] = {}
    grouped_external: dict[str,list[Record]] = {}
    for record, bucket in [(x,grouped_internal) for x in internal] + [(x,grouped_external) for x in external]:
        reference(record.operation_id)
        reference(record.provider_reference)
        if record.status not in {'settled','failed','unknown','reversed'} or not record.provider:
            raise ContractError('Invalid reconciliation input')
        bucket.setdefault(record.operation_id, []).append(record)
    findings = []
    for key in sorted(set(grouped_internal) | set(grouped_external)):
        left, right = grouped_internal.get(key, []), grouped_external.get(key, [])
        if len(left)>1:
            decision = Decision.DUPLICATE_INTERNAL
        elif len(right)>1:
            decision = Decision.DUPLICATE_PROVIDER
        elif not left:
            decision = Decision.MISSING_INTERNAL
        elif not right:
            decision = Decision.MISSING_PROVIDER
        elif left[0].tenant != right[0].tenant:
            decision = Decision.TENANT_MISMATCH
        elif left[0].provider != right[0].provider or left[0].provider_reference != right[0].provider_reference:
            decision = Decision.PROVIDER_MISMATCH
        elif left[0].money.currency != right[0].money.currency:
            decision = Decision.CURRENCY_MISMATCH
        elif left[0].money.value != right[0].money.value:
            decision = Decision.AMOUNT_MISMATCH
        elif left[0].status != 'settled' or right[0].status != 'settled':
            decision = Decision.UNKNOWN_OUTCOME
        else:
            decision = Decision.MATCHED
        findings.append(Finding(key, decision, decision != Decision.MATCHED))
    return tuple(findings)
