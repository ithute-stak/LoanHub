"""Offline-only, fail-closed preparation for a new-only client loan handoff.

This module is NEVER a loan origination authorization. It inspects scoped
account provenance without creating a loan, drafting an application, or
modifying historical financial records. No public router imports it.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.company_client import CompanyBorrowerAccount
from database.models.new_client_registration_attempt import NewClientRegistrationAttempt
from routers.batlokoa_registration_availability import registration_availability_for_staff


class NewOnlyLoanHandoffDenied(ValueError):
    pass


@dataclass(frozen=True)
class NewOnlyLoanHandoffAssessment:
    registration_provenance_confirmed: bool
    scoped_branch_confirmed: bool
    registration_completed: bool
    requires_kyc_verification: bool = True
    requires_affordability_assessment: bool = True
    requires_credit_approval: bool = True
    can_create_loan_application: bool = False
    can_disburse_loan: bool = False
    loan_application_created: bool = False


def assess_new_only_loan_handoff(
    db: Session,
    *,
    context: TenantContext,
    account_id: UUID,
) -> NewOnlyLoanHandoffAssessment:
    """Read only; raises for untrusted, existing or wrong-branch accounts.

    The account MUST be newly created by the protected new-only path, match
    this employee/company/branch, and have a completed linked idempotency
    reservation. This is deliberately stricter than a generic company
    borrower lookup: legacy assisted accounts may have historical loans.
    """
    registration_availability_for_staff(context)
    if not isinstance(account_id, UUID) or not isinstance(context.branch_id, UUID):
        raise NewOnlyLoanHandoffDenied("A selected, authorized branch is required")
    if (
        db.get_bind() is None
        or db.get_bind().dialect.name != "postgresql"
    ):
        raise NewOnlyLoanHandoffDenied("PostgreSQL required for provenance checks")

    account = db.execute(
        select(CompanyBorrowerAccount).where(
            CompanyBorrowerAccount.id == account_id,
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.branch_id == context.branch_id,
            CompanyBorrowerAccount.source == "new_only_registration",
        )
    ).scalar_one_or_none()
    if (
        account is None
        or account.id != account_id
        or account.company_id != context.company_id
        or account.branch_id != context.branch_id
        or account.source != "new_only_registration"
        or not isinstance(account.borrower_id, UUID)
        or account.opened_by_user_id != context.user.id
    ):
        raise NewOnlyLoanHandoffDenied("New-only registration scope not established")

    attempt = db.execute(
        select(NewClientRegistrationAttempt).where(
            NewClientRegistrationAttempt.company_id == context.company_id,
            NewClientRegistrationAttempt.branch_id == context.branch_id,
            NewClientRegistrationAttempt.employee_user_id == context.user.id,
            NewClientRegistrationAttempt.client_account_id == account.id,
            NewClientRegistrationAttempt.status == "completed",
        )
    ).scalar_one_or_none()
    if (
        attempt is None
        or attempt.company_id != context.company_id
        or attempt.branch_id != context.branch_id
        or attempt.employee_user_id != context.user.id
        or attempt.client_account_id != account.id
        or attempt.status != "completed"
        or attempt.finalized_at is None
    ):
        raise NewOnlyLoanHandoffDenied("Completed new-only registration required")

    # Verified provenance is NOT underwriting or authorization. This
    # component never originates a draft or performs a loan-calculator call.
    return NewOnlyLoanHandoffAssessment(
        registration_provenance_confirmed=True,
        scoped_branch_confirmed=True,
        registration_completed=True,
    )
