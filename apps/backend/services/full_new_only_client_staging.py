"""Phase 85: restricted full-profile staging inside a caller-owned transaction.

INTERNAL ONLY. Not connected to a FastAPI route or the atomic registration
writer. Its caller must first stage a genuinely new borrower/account using
the certified new-only transaction, then provide the resulting IDs.

Never commits and never links a historic borrower. Unsupported fields are
rejected before any mutation. Full end-to-end certification is still required.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.borrower import Borrower
from database.models.person import Person
from database.models.company_client import CompanyBorrowerAccount
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services.new_only_client_staging import StagedNewClient
from services.company_client_service import (
    _save_assisted_banking_profile, save_assisted_external_debts,
)


class FullNewOnlyStagingUnavailable(RuntimeError):
    pass


def _reject_unsafe_fields(payload: FullNewOnlyClientCapture) -> None:
    """Fail closed on fields whose semantics are not yet covered by this path.

    A stored bank account is deliberately left UNVERIFIED; the submitted
    request must not contain purportedly verified information. Loan status
    is also not inferred from an applicant-controlled confirmation.
    """
    if not isinstance(payload, FullNewOnlyClientCapture):
        raise FullNewOnlyStagingUnavailable("Validated full capture required")
    if (
        payload.email is not None
        or payload.temporary_password is not None
        or payload.employer_group_id is not None
        or payload.new_employer_group is not None
        or payload.cdas_employee_number
    ):
        raise FullNewOnlyStagingUnavailable(
            "Identity email, credentials, employer group or CDAS payroll "
            "require separately certified registration workflows"
        )
    if payload.bank_account is not None and (
        payload.bank_account.id is not None
        or payload.bank_account.verification_status != "unverified"
        or payload.bank_account.verification_reference is not None
        or not payload.bank_account.account_number
    ):
        raise FullNewOnlyStagingUnavailable(
            "Only new, unverified bank account details can be staged"
        )
    if payload.has_existing_loans and not payload.external_debts:
        raise FullNewOnlyStagingUnavailable(
            "Existing obligations require structured debt details"
        )
    if payload.external_debts:
        # Never turn applicant-entered claims into verified obligations.
        if any(debt.is_verified for debt in payload.external_debts):
            raise FullNewOnlyStagingUnavailable(
                "Applicant-declared external debts cannot be verified"
            )
        current = sum((debt.current_balance for debt in payload.external_debts),
                      Decimal("0"))
        if current != payload.existing_loan_total:
            raise FullNewOnlyStagingUnavailable(
                "Structured external debt balances must match declared total"
            )
    for item in payload.external_debts:
        # Preserve the explicit submitted loan lifecycle status. The shared
        # legacy helper changes zero-balance rows to settled; do not allow
        # this writer to silently reinterpret applicant-supplied status.
        if item.current_balance <= 0 and item.status != "settled":
            raise FullNewOnlyStagingUnavailable(
                "Zero-balance debt status requires independent review"
            )


def stage_full_new_only_client_details(
    db: Session,
    *,
    payload: FullNewOnlyClientCapture,
    staged: StagedNewClient,
    actor_user_id: UUID,
    approved_internal_call: bool = False,
) -> None:
    """Stage ONLY additional data for a newly created client; never commit.

    Does not create accounts or originate a loan. All operations use the
    caller-owned Session transaction and must roll back with base staging.
    """
    if approved_internal_call is not True:
        raise FullNewOnlyStagingUnavailable("Internal new-only staging is disabled")
    _reject_unsafe_fields(payload)
    if not isinstance(staged, StagedNewClient):
        raise FullNewOnlyStagingUnavailable("New-only staging evidence required")
    if (
        db.get_bind() is None
        or db.get_bind().dialect.name != "postgresql"
        or not db.in_transaction()
        or payload.branch_id != staged.branch_id
        or not isinstance(actor_user_id, UUID)
    ):
        raise FullNewOnlyStagingUnavailable(
            "Same PostgreSQL transaction, new-only company and branch required"
        )

    # An existing historical/linked borrower is never an authorized target.
    # This check is necessary, not sufficient: the containing atomic writer
    # must independently prove the base borrower was created in this tx.
    account = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.id == staged.client_account_id,
        CompanyBorrowerAccount.borrower_id == staged.borrower_id,
        CompanyBorrowerAccount.company_id == staged.company_id,
        CompanyBorrowerAccount.branch_id == staged.branch_id,
        CompanyBorrowerAccount.source == "new_only_registration",
        CompanyBorrowerAccount.opened_by_user_id == actor_user_id,
    ).one_or_none()
    if account is None:
        raise FullNewOnlyStagingUnavailable("New-only account scope mismatch")

    person = db.query(Person).filter(
        Person.user_id == staged.user_id
    ).one_or_none()
    borrower = db.query(Borrower).filter(
        Borrower.id == staged.borrower_id,
        Borrower.user_id == staged.user_id,
    ).one_or_none()
    if person is None or borrower is None:
        raise FullNewOnlyStagingUnavailable("Staged new identity is incomplete")

    # The minimal writer already saved the mandatory core fields. These
    # are the remaining supported optional fields only.
    person.middle_name = payload.middle_name
    person.marital_status = payload.marital_status
    person.nationality = payload.nationality
    person.town_or_village = payload.town_or_village
    person.physical_address = payload.physical_address
    borrower.employment_type = payload.employment_type
    borrower.employer_name = payload.employer_name
    borrower.income_day = payload.income_day
    borrower.job_title = payload.job_title
    borrower.monthly_income = payload.monthly_income
    borrower.salary_date = payload.salary_date

    # The bank service encrypts the account number and tokenized provider
    # reference and marks the account unverified. It does not commit.
    _save_assisted_banking_profile(
        db,
        borrower=borrower,
        company_id=staged.company_id,
        bank_input=payload.bank_account,
    )

    # External declared debts are separate borrower obligations, not
    # LoanHub loans or repayments. This helper also never commits.
    save_assisted_external_debts(
        db,
        borrower=borrower,
        company_id=staged.company_id,
        user_id=actor_user_id,
        debts=payload.external_debts,
        legacy_total=payload.existing_loan_total,
        legacy_has_existing_loans=payload.has_existing_loans,
    )
    db.flush()
