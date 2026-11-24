"""Internal offline loan application *preflight*, never an origination command.

Every check is advisory and read only. A successful result is not a
permission to create an application or disburse money. No API imports it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.company_client import CompanyBorrowerAccount
from database.models.loan_product import LoanProduct
from database.models.professional_lending import DirectLoanApplication
from services.batlokoa_new_only_loan_handoff import (
    NewOnlyLoanHandoffDenied,
    assess_new_only_loan_handoff,
)


@dataclass(frozen=True)
class NewOnlyApplicationPreflight:
    new_only_provenance_confirmed: bool
    product_in_company_confirmed: bool
    amount_in_product_range: bool
    term_in_product_range: bool
    no_existing_origination_applications: bool
    requires_identity_and_kyc_review: bool = True
    requires_affordability_assessment: bool = True
    requires_underwriting_and_credit_approval: bool = True
    requires_independent_release_approval: bool = True
    can_create_loan_application: bool = False
    can_disburse_loan: bool = False
    wrote_financial_records: bool = False


def assess_new_only_application_preflight(
    db: Session,
    *,
    context: TenantContext,
    account_id: UUID,
    product_id: UUID,
    requested_amount: Decimal,
    term_count: int,
) -> NewOnlyApplicationPreflight:
    """Fail closed on invalid fields, wrong product or any prior origination.

    The comprehensive registration provenance verifier runs first. The
    product must be active and belong to this exact company. Any existing
    application for this borrower/company blocks this conservative preflight,
    regardless of whether it was rejected or closed; this is deliberate
    until a separate repeat-loan policy is certified. This avoids treating
    any historic borrower account or application as a brand-new borrower.
    """
    assess_new_only_loan_handoff(
        db, context=context, account_id=account_id,
    )
    if (
        not isinstance(product_id, UUID)
        or type(requested_amount) is not Decimal
        or not requested_amount.is_finite()
        or requested_amount <= 0
        or requested_amount.as_tuple().exponent < -2
        or type(term_count) is not int
        or not 1 <= term_count <= 120
    ):
        raise NewOnlyLoanHandoffDenied("Valid product, principal and term required")

    account = db.execute(
        select(CompanyBorrowerAccount).where(
            CompanyBorrowerAccount.id == account_id,
            CompanyBorrowerAccount.company_id == context.company_id,
            CompanyBorrowerAccount.branch_id == context.branch_id,
            CompanyBorrowerAccount.source == "new_only_registration",
            CompanyBorrowerAccount.opened_by_user_id == context.user.id,
        )
    ).scalar_one_or_none()
    if (
        account is None
        or account.id != account_id
        or account.company_id != context.company_id
        or account.branch_id != context.branch_id
        or account.source != "new_only_registration"
        or account.opened_by_user_id != context.user.id
        or not isinstance(account.borrower_id, UUID)
    ):
        raise NewOnlyLoanHandoffDenied("Scoped new-only account required")

    product = db.execute(
        select(LoanProduct).where(
            LoanProduct.id == product_id,
            LoanProduct.company_id == context.company_id,
            LoanProduct.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if (
        product is None
        or product.id != product_id
        or product.company_id != context.company_id
        or product.is_active is not True
    ):
        raise NewOnlyLoanHandoffDenied("Active tenant-owned loan product required")

    if any(
        type(value) is not Decimal or not value.is_finite()
        for value in (product.min_amount, product.max_amount)
    ):
        raise NewOnlyLoanHandoffDenied("Product financial configuration invalid")
    if (
        product.min_amount <= 0
        or product.max_amount < product.min_amount
        or not product.min_amount <= requested_amount <= product.max_amount
    ):
        raise NewOnlyLoanHandoffDenied("Requested amount outside approved product bounds")
    if (
        type(product.min_term_months) is not int
        or type(product.max_term_months) is not int
        or product.min_term_months < 1
        or product.max_term_months < product.min_term_months
        or not product.min_term_months <= term_count <= product.max_term_months
    ):
        raise NewOnlyLoanHandoffDenied("Requested term outside approved product bounds")

    # Check ALL companies and statuses: a supposedly brand-new borrower
    # cannot inherit any historical origination application anywhere.
    # This read is NOT a concurrent uniqueness/serialization guarantee.
    existing = db.execute(
        select(DirectLoanApplication.id).where(
            DirectLoanApplication.borrower_id == account.borrower_id,
        ).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        raise NewOnlyLoanHandoffDenied(
            "Existing origination application requires independent review"
        )

    return NewOnlyApplicationPreflight(
        new_only_provenance_confirmed=True,
        product_in_company_confirmed=True,
        amount_in_product_range=True,
        term_in_product_range=True,
        no_existing_origination_applications=True,
    )
