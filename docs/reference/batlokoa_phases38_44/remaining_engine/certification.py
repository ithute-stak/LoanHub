"""Phase 41 release readiness evidence checklist; cannot deploy or enable flags."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import ContractError

REQUIRED = frozenset({
    'reviewed_migrations', 'postgres_rls', 'concurrency', 'audit_anchoring',
    'approved_mandates', 'provider_live_certification', 'signed_webhooks',
    'reconciliation', 'double_entry', 'rollback_drill', 'backup_restore',
    'incident_response', 'financial_legal_approval', 'operator_access_review',
})

@dataclass(frozen=True, slots=True)
class Gate:
    name: str
    passed: bool
    evidence_reference: str

@dataclass(frozen=True, slots=True)
class Certification:
    ready_for_review: bool
    missing: tuple[str,...]
    failed: tuple[str,...]


def assess(gates: tuple[Gate, ...]) -> Certification:
    names = [x.name for x in gates]
    if len(names) != len(set(names)):
        raise ContractError('Duplicate certification evidence')
    present = set(names)
    if present - REQUIRED:
        raise ContractError('Unrecognized certification gate')
    missing = tuple(sorted(REQUIRED-present))
    failed = tuple(sorted(x.name for x in gates if not x.passed or not x.evidence_reference.strip()))
    return Certification(not missing and not failed, missing, failed)
