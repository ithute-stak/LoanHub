"""Consent-bound Principal x% collection coordination — adapter contract only.

NOT a production endpoint. A trusted database adapter must implement one
transaction with a real loan row lock, authoritative cross-source reconciliation,
verified consent evidence, durable uniqueness, and provider finality. There is
no production adapter registered by this module.
"""
from datetime import datetime
from typing import Protocol

from payment_engine.principal_x_collection_ceiling import require_collection_within_ceiling
from payment_engine.principal_x_provider_finality import (
    ProviderFinalityEvidence, require_provider_finality,
)
from payment_engine.principal_x_settlement_consent import (
    BorrowerAcceptance, SettlementOffer,
)
from services.principal_x_settlement_acceptance_preflight import (
    preflight_principal_x_settlement_acceptance,
)
from services.principal_x_settlement_preview_service import PrincipalXSnapshotQuote
from services.principal_x_transaction_coordinator import (
    CollectionPostingResult, LockedLoanSnapshot, VerifiedCollection,
)


class ConsentBoundTransaction(Protocol):
    """All trusted reads and writes must share an actual DB loan lock."""

    def __enter__(self): ...
    def __exit__(self, exc_type, exc_value, traceback): ...
    def lock_loan_and_reconcile(self, *, company_id, loan_id) -> LockedLoanSnapshot: ...
    def read_authoritative_ledger_revision(self, *, company_id, loan_id) -> str: ...
    def read_current_quote_under_lock(
        self, *, company_id, loan_id, settlement_date,
    ) -> PrincipalXSnapshotQuote: ...
    def verify_borrower_acceptance_evidence(
        self, *, acceptance: BorrowerAcceptance,
    ) -> None: ...
    def obtain_verified_provider_evidence(
        self, *, provider_reference: str,
    ) -> ProviderFinalityEvidence: ...
    def reserve_unique_collection(
        self, *, idempotency_key: str, provider_reference: str,
    ) -> None: ...
    def persist_collection(self, *, instruction: VerifiedCollection) -> str: ...


def coordinate_consent_bound_principal_x_settlement(
    *, transaction: ConsentBoundTransaction,
    instruction: VerifiedCollection,
    offer: SettlementOffer,
    acceptance: BorrowerAcceptance,
    quoted_snapshot_revision: str,
    settlement_date,
    now: datetime,
) -> CollectionPostingResult:
    """Fail closed before any reservation or write if evidence is invalid.

    Adapter correctness cannot be proved by this orchestration; especially
    authoritative source coverage, physical row locking, actual borrower
    evidence verification, unique DB constraints, and commit/rollback.
    """
    if instruction.company_id != offer.company_id or instruction.loan_id != offer.loan_id:
        raise ValueError("Collection instruction does not match settlement offer")
    if instruction.amount != offer.quote.collectible_due:
        raise ValueError("Collection amount must equal accepted settlement quote")
    if not all((
        instruction.idempotency_key and instruction.idempotency_key.strip(),
        instruction.provider_reference and instruction.provider_reference.strip(),
        instruction.verification_reference and instruction.verification_reference.strip(),
    )):
        raise ValueError("Collection idempotency and provider references required")

    with transaction as tx:
        snapshot = tx.lock_loan_and_reconcile(
            company_id=instruction.company_id, loan_id=instruction.loan_id,
        )
        if snapshot.company_id != instruction.company_id or snapshot.loan_id != instruction.loan_id:
            raise ValueError("Locked snapshot loan/company mismatch")
        if not snapshot.reconciled or not snapshot.live_policy_enabled:
            raise ValueError("Certified reconciliation and active policy required")
        revision = tx.read_authoritative_ledger_revision(
            company_id=instruction.company_id, loan_id=instruction.loan_id,
        )
        current_quote = tx.read_current_quote_under_lock(
            company_id=instruction.company_id,
            loan_id=instruction.loan_id,
            settlement_date=settlement_date,
        )
        preflight_principal_x_settlement_acceptance(
            offer=offer,
            acceptance=acceptance,
            quoted_snapshot_revision=quoted_snapshot_revision,
            current_snapshot=current_quote,
            authoritative_ledger_revision=revision,
            now=now,
        )
        # Consent authenticity must be established by a trusted server-side
        # adapter, NEVER from caller-supplied "verified_identity" alone.
        tx.verify_borrower_acceptance_evidence(acceptance=acceptance)
        evidence = tx.obtain_verified_provider_evidence(
            provider_reference=instruction.provider_reference,
        )
        require_provider_finality(
            evidence=evidence,
            company_id=instruction.company_id,
            loan_id=instruction.loan_id,
            expected_amount=instruction.amount,
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
        payment_reference = tx.persist_collection(instruction=instruction)
        if not isinstance(payment_reference, str) or not payment_reference.strip():
            raise ValueError("Persisted collection reference required")
        return CollectionPostingResult(payment_reference=payment_reference, ceiling=ceiling)
