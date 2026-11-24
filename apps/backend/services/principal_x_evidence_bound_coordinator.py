"""Strict evidence-bound Principal x collection coordination.

A trusted transaction adapter retrieves finality evidence server-side inside
the locked transaction. This is an opt-in integration boundary, not a live
payment route. Provider evidence must not be supplied by an API caller.
"""
from dataclasses import dataclass
from typing import Protocol

from payment_engine.principal_x_collection_ceiling import require_collection_within_ceiling
from payment_engine.principal_x_provider_finality import (
    ProviderFinalityEvidence, require_provider_finality,
)
from services.principal_x_transaction_coordinator import (
    CollectionPostingResult, LockedLoanSnapshot, VerifiedCollection,
)


class EvidenceBoundTransaction(Protocol):
    def __enter__(self): ...
    def __exit__(self, exc_type, exc_value, traceback): ...
    def lock_loan_and_reconcile(self, *, company_id, loan_id) -> LockedLoanSnapshot: ...
    def obtain_verified_provider_evidence(
        self, *, provider_reference: str,
    ) -> ProviderFinalityEvidence: ...
    def reserve_unique_collection(
        self, *, idempotency_key: str, provider_reference: str,
    ) -> None: ...
    def persist_collection(self, *, instruction: VerifiedCollection) -> str: ...


def coordinate_evidence_bound_collection(
    *, transaction: EvidenceBoundTransaction, instruction: VerifiedCollection,
) -> CollectionPostingResult:
    """Enforce provider evidence, cap, uniqueness and persistence in one scope.

    Requires an adapter with real DB locking, independently authenticated
    provider verification, unique DB constraints, rollback and commit.
    """
    if not instruction.idempotency_key or not instruction.idempotency_key.strip():
        raise ValueError("Idempotency key required")
    if not instruction.provider_reference or not instruction.provider_reference.strip():
        raise ValueError("Provider reference required")
    if not instruction.verification_reference or not instruction.verification_reference.strip():
        raise ValueError("Verification reference required")
    with transaction as tx:
        snapshot = tx.lock_loan_and_reconcile(
            company_id=instruction.company_id, loan_id=instruction.loan_id,
        )
        if snapshot.company_id != instruction.company_id or snapshot.loan_id != instruction.loan_id:
            raise ValueError("Locked loan/company mismatch")
        if not snapshot.reconciled or not snapshot.live_policy_enabled:
            raise ValueError("Reconciled ledger and live policy required")
        evidence = tx.obtain_verified_provider_evidence(
            provider_reference=instruction.provider_reference,
        )
        require_provider_finality(
            evidence=evidence, company_id=instruction.company_id,
            loan_id=instruction.loan_id, expected_amount=instruction.amount,
            expected_provider_reference=instruction.provider_reference,
            expected_idempotency_key=instruction.idempotency_key,
        )
        if evidence.verification_reference != instruction.verification_reference:
            raise ValueError("Provider verification reference mismatch")
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
