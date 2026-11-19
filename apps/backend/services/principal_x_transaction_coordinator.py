"""Fail-closed transaction coordinator for future Principal x posting.

This module defines an integration boundary, not a production payment endpoint.
The adapter MUST implement a real row lock, authoritative reconciliation,
provider finality, and durable uniqueness in one DB transaction. No adapter
is supplied here; in-memory locking or caller-provided booleans are forbidden.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from payment_engine.principal_x_collection_ceiling import (
    CollectionCeiling, require_collection_within_ceiling,
)


@dataclass(frozen=True)
class VerifiedCollection:
    company_id: UUID
    loan_id: UUID
    amount: Decimal
    idempotency_key: str
    provider_reference: str
    verification_reference: str


@dataclass(frozen=True)
class LockedLoanSnapshot:
    company_id: UUID
    loan_id: UUID
    original_principal: Decimal
    authoritative_net_collected: Decimal
    live_policy_enabled: bool
    reconciled: bool


class PrincipalXTransaction(Protocol):
    """Database adapter holding the loan row lock until transaction exit."""

    def __enter__(self): ...
    def __exit__(self, exc_type, exc_value, traceback): ...
    def lock_loan_and_reconcile(self, *, company_id: UUID, loan_id: UUID) -> LockedLoanSnapshot: ...
    def assert_provider_final(self, *, provider_reference: str, verification_reference: str) -> None: ...
    def reserve_unique_collection(self, *, idempotency_key: str, provider_reference: str) -> None: ...
    def persist_collection(self, *, instruction: VerifiedCollection) -> str: ...


@dataclass(frozen=True)
class CollectionPostingResult:
    payment_reference: str
    ceiling: CollectionCeiling


def coordinate_principal_x_collection(
    *, transaction: PrincipalXTransaction, instruction: VerifiedCollection,
) -> CollectionPostingResult:
    """Coordinate all checks and persistence under a single DB transaction.

    The adapter's context manager must roll back on any exception, including
    commit failures, and must not suppress exceptions. The adapter must
    acquire an actual DB row lock before returning the snapshot. This
    orchestration cannot independently verify adapter correctness.
    """
    if not isinstance(instruction.company_id, UUID) or not isinstance(instruction.loan_id, UUID):
        raise ValueError("Verified company and loan UUIDs required")
    if not instruction.idempotency_key or not instruction.idempotency_key.strip():
        raise ValueError("Durable idempotency key required")
    if not instruction.provider_reference or not instruction.provider_reference.strip():
        raise ValueError("Provider reference required")
    if not instruction.verification_reference or not instruction.verification_reference.strip():
        raise ValueError("Provider verification evidence required")
    with transaction as tx:
        snapshot = tx.lock_loan_and_reconcile(
            company_id=instruction.company_id, loan_id=instruction.loan_id,
        )
        if snapshot.company_id != instruction.company_id or snapshot.loan_id != instruction.loan_id:
            raise ValueError("Locked snapshot loan/company mismatch")
        if not snapshot.reconciled or not snapshot.live_policy_enabled:
            raise ValueError("Reconciled ledger and enabled live policy required")
        tx.assert_provider_final(
            provider_reference=instruction.provider_reference,
            verification_reference=instruction.verification_reference,
        )
        ceiling = require_collection_within_ceiling(
            original_principal=snapshot.original_principal,
            net_collected=snapshot.authoritative_net_collected,
            proposed_collection=instruction.amount,
        )
        tx.reserve_unique_collection(
            idempotency_key=instruction.idempotency_key,
            provider_reference=instruction.provider_reference,
        )
        reference = tx.persist_collection(instruction=instruction)
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Persisted payment reference required")
        return CollectionPostingResult(payment_reference=reference, ceiling=ceiling)
