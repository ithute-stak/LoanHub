"""PostgreSQL read-only locked Principal x loan snapshot.

This is a staging integration building block, NOT a payment writer. It acquires
a real PostgreSQL FOR UPDATE loan-row lock and verifies company policy and
immutable loan assignment. It deliberately refuses to certify reconciled
collections until provider reversals/refunds have a proven authoritative
ledger implementation. Never use it to enable live collections.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_payment_model_settings import CompanyPaymentModelSettings
from database.models.loan_payment_model_assignment import LoanPaymentModelAssignmentRecord
from database.models.payment import PaymentTransaction
from payment_engine.principal_x_policy import PaymentModel
from services.principal_x_transaction_coordinator import LockedLoanSnapshot
from services.principal_x_collection_source_diagnostics import (
    CollectionSourceDiagnostics, inspect_principal_x_collection_sources,
)
from services.principal_x_payment_evidence_adapter import (
    LoanHubPaymentAudit, inspect_loanhub_payment_evidence,
)


def lock_principal_x_loan_for_review(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> LockedLoanSnapshot:
    """Acquire row lock in caller's open transaction; never commit or post.

    PostgreSQL-only. A missing policy or assignment is disabled, never
    implicitly upgraded. All payments, even pending/failed, prevent claiming
    that the historical ledger is reconciled.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Company and loan UUIDs required")
    if db.get_bind().dialect.name != "postgresql":
        raise ValueError("PostgreSQL required for loan row locking")
    loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.company_id == company_id)
        .with_for_update()
        .one_or_none()
    )
    if loan is None:
        raise ValueError("Loan not found within company")
    policy = (
        db.query(CompanyPaymentModelSettings)
        .filter(CompanyPaymentModelSettings.company_id == company_id)
        .one_or_none()
    )
    assignment = (
        db.query(LoanPaymentModelAssignmentRecord)
        .filter(
            LoanPaymentModelAssignmentRecord.loan_id == loan_id,
            LoanPaymentModelAssignmentRecord.company_id == company_id,
        )
        .one_or_none()
    )
    enabled = bool(
        policy is not None
        and policy.allow_new_loans is True
        and policy.enable_live_collections is True
        and policy.default_model == PaymentModel.PRINCIPAL_X.value
        and assignment is not None
        and assignment.payment_model == PaymentModel.PRINCIPAL_X.value
    )
    # This query is intentionally a conservative diagnostic, not a net ledger.
    payment_count = (
        db.query(PaymentTransaction.id)
        .filter(PaymentTransaction.company_id == company_id, PaymentTransaction.loan_id == loan_id)
        .count()
    )
    # Even an empty payment history is NOT proof that there are no manual,
    # legacy, external, or refunded collections. No adapter may rely on it.
    _ = payment_count
    return LockedLoanSnapshot(
        company_id=company_id,
        loan_id=loan_id,
        original_principal=Decimal(str(loan.principal_amount)),
        authoritative_net_collected=Decimal("0.00"),
        live_policy_enabled=enabled,
        reconciled=False,
    )


@dataclass(frozen=True)
class LockedCollectionEvidenceReview:
    """Non-payable diagnostics obtained after a PostgreSQL loan-row lock."""
    snapshot: LockedLoanSnapshot
    payment_audit: LoanHubPaymentAudit
    source_diagnostics: CollectionSourceDiagnostics
    can_post: bool = False


def inspect_principal_x_sources_under_loan_lock(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> LockedCollectionEvidenceReview:
    """Hold the caller's transaction/loan lock while reading linked sources.

    Caller owns the transaction boundary and must not commit until finished.
    This does not protect against writers that ignore the loan-row lock or
    certify external provider, refund, legacy or manual payment sources.
    """
    snapshot = lock_principal_x_loan_for_review(
        db, company_id=company_id, loan_id=loan_id,
    )
    audit = inspect_loanhub_payment_evidence(
        db, company_id=company_id, loan_id=loan_id,
    )
    sources = inspect_principal_x_collection_sources(
        db, company_id=company_id, loan_id=loan_id,
    )
    return LockedCollectionEvidenceReview(
        snapshot=snapshot,
        payment_audit=audit,
        source_diagnostics=sources,
        can_post=False,
    )
