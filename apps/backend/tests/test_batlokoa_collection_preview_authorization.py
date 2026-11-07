from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from core.access_control import TenantContext
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, UserRole
from services.batlokoa_collection_preview_authorization import (
    BatlokoaCollectionAuthorizationError,
    authorize_batlokoa_collection_preview,
)

COMPANY = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
OTHER = UUID("00000000-0000-4000-8000-000000000002")
BRANCH = UUID("00000000-0000-4000-8000-000000000003")
OTHER_BRANCH = UUID("00000000-0000-4000-8000-000000000004")
LOAN_ID = UUID("00000000-0000-4000-8000-000000000005")
BORROWER_ID = UUID("00000000-0000-4000-8000-000000000006")
BORROWER_USER = UUID("00000000-0000-4000-8000-000000000007")


def make_state(role=UserRole.COLLECTIONS_OFFICER):
    staff = SimpleNamespace(
        is_active=True, company_id=COMPANY, branch_id=BRANCH, role=role,
    )
    context = TenantContext(
        user=SimpleNamespace(is_active=True, role=role),
        staff=staff, company=None, company_id=COMPANY,
        branch_id=BRANCH, is_platform_admin=False,
    )
    loan = SimpleNamespace(
        id=LOAN_ID, company_id=COMPANY, branch_id=BRANCH,
        borrower_id=BORROWER_ID, status=LoanStatus.ACTIVE,
        disbursed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        balance=Decimal("250.00"),
    )
    borrower = SimpleNamespace(id=BORROWER_ID, user_id=BORROWER_USER)

    class FakeDB:
        def get(self, model, identifier):
            if model is ClientCompanyLoan and identifier == LOAN_ID:
                return loan
            if model is Borrower and identifier == BORROWER_ID:
                return borrower
            return None

        def add(self, *args):
            raise AssertionError("Authorization must not persist data")

        def commit(self):
            raise AssertionError("Authorization must not commit")

    return FakeDB(), context, loan, borrower


def authorize(db, context, amount="100.00", borrower_user_id=BORROWER_USER):
    return authorize_batlokoa_collection_preview(
        db=db, context=context, loan_id=LOAN_ID,
        borrower_user_id=borrower_user_id, amount=amount,
    )


def test_authorized_active_batlokoa_loan_returns_opaque_nonposting_scope():
    db, context, loan, borrower = make_state()
    proof = authorize(db, context)
    assert proof.company_id == str(COMPANY)
    assert proof.loan_id == str(LOAN_ID)
    assert proof.borrower_id == str(BORROWER_ID)
    assert proof.amount == "100.00"
    assert proof.currency == "LSL"
    assert proof.source_reference == f"loan_{LOAN_ID.hex}"
    assert proof.payment_execution_enabled is False


def test_management_may_view_company_loan_across_branches():
    db, context, loan, borrower = make_state(UserRole.COMPANY_OWNER)
    loan.branch_id = OTHER_BRANCH
    assert authorize(db, context).amount == "100.00"


@pytest.mark.parametrize("change", [
    "inactive_user", "inactive_staff", "wrong_company",
    "wrong_membership_company", "platform_admin", "no_staff",
    "disallowed_role", "cross_branch", "unscoped_branch",
    "cross_company_loan", "wrong_loan_borrower", "wrong_borrower_user",
    "undisbursed", "completed", "zero_balance", "negative_balance",
])
def test_unauthorized_borrower_company_branch_and_loan_fail_closed(change):
    db, context, loan, borrower = make_state()
    borrower_user_id = BORROWER_USER
    if change == "inactive_user":
        context.user.is_active = False
    elif change == "inactive_staff":
        context.staff.is_active = False
    elif change == "wrong_company":
        context = TenantContext(
            user=context.user, staff=context.staff, company=None,
            company_id=OTHER, branch_id=BRANCH, is_platform_admin=False,
        )
    elif change == "wrong_membership_company":
        context.staff.company_id = OTHER
    elif change == "platform_admin":
        context = TenantContext(
            user=context.user, staff=context.staff, company=None,
            company_id=COMPANY, branch_id=BRANCH, is_platform_admin=True,
        )
    elif change == "no_staff":
        context = TenantContext(
            user=context.user, staff=None, company=None,
            company_id=COMPANY, branch_id=BRANCH, is_platform_admin=False,
        )
    elif change == "disallowed_role":
        context.staff.role = UserRole.CUSTOMER_SUPPORT
    elif change == "cross_branch":
        loan.branch_id = OTHER_BRANCH
    elif change == "unscoped_branch":
        context = TenantContext(
            user=context.user, staff=context.staff, company=None,
            company_id=COMPANY, branch_id=None, is_platform_admin=False,
        )
    elif change == "cross_company_loan":
        loan.company_id = OTHER
    elif change == "wrong_loan_borrower":
        loan.borrower_id = OTHER
    elif change == "wrong_borrower_user":
        borrower_user_id = OTHER
    elif change == "undisbursed":
        loan.disbursed_at = None
    elif change == "completed":
        loan.status = LoanStatus.COMPLETED
    elif change == "zero_balance":
        loan.balance = Decimal("0.00")
    elif change == "negative_balance":
        loan.balance = Decimal("-50.00")
    with pytest.raises(BatlokoaCollectionAuthorizationError):
        authorize(db, context, borrower_user_id=borrower_user_id)


@pytest.mark.parametrize("amount", [
    "0.00", "-1.00", "250.01", "1.001", "NaN",
    "Infinity", "not-a-number", "99999999999999999",
])
def test_noncollectible_amounts_are_rejected(amount):
    db, context, *_ = make_state()
    with pytest.raises(BatlokoaCollectionAuthorizationError):
        authorize(db, context, amount=amount)


def test_valid_defaulted_loan_is_eligible_for_preview_only():
    db, context, loan, _ = make_state()
    loan.status = LoanStatus.DEFAULTED
    assert authorize(db, context, amount="200.00").payment_execution_enabled is False
