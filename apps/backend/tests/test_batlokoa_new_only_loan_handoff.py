"""Offline new-only loan handoff never creates a loan or touches legacy data."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from core.access_control import TenantContext
from database.models.enums import CompanyStatus, UserRole
from services.batlokoa_new_only_loan_handoff import (
    NewOnlyLoanHandoffDenied,
    assess_new_only_loan_handoff,
)


def staff():
    actor, company, branch = uuid4(), uuid4(), uuid4()
    return TenantContext(
        user=SimpleNamespace(id=actor, is_active=True, role=UserRole.LOAN_OFFICER),
        staff=SimpleNamespace(
            user_id=actor, company_id=company, branch_id=branch,
            role=UserRole.LOAN_OFFICER, is_active=True,
        ),
        company=SimpleNamespace(
            id=company, status=CompanyStatus.APPROVED, is_active=True,
        ),
        company_id=company, branch_id=branch, is_platform_admin=False,
    )


def real_provenance(context, account_id):
    account = SimpleNamespace(
        id=account_id, company_id=context.company_id,
        branch_id=context.branch_id, source="new_only_registration",
        borrower_id=uuid4(), opened_by_user_id=context.user.id,
    )
    attempt = SimpleNamespace(
        company_id=context.company_id, branch_id=context.branch_id,
        employee_user_id=context.user.id, client_account_id=account_id,
        status="completed", finalized_at=datetime.now(timezone.utc),
    )
    return account, attempt


def fake_db(account, attempt):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
    )
    db.execute.return_value.scalar_one_or_none.side_effect = [account, attempt]
    return db


def test_completed_same_employee_registration_only_allows_nonwriting_readiness():
    ctx, account_id = staff(), uuid4()
    account, attempt = real_provenance(ctx, account_id)
    db = fake_db(account, attempt)
    result = assess_new_only_loan_handoff(db, context=ctx, account_id=account_id)
    assert result.registration_provenance_confirmed is True
    assert result.scoped_branch_confirmed is True
    assert result.registration_completed is True
    assert result.requires_kyc_verification is True
    assert result.requires_affordability_assessment is True
    assert result.requires_credit_approval is True
    assert result.can_create_loan_application is False
    assert result.can_disburse_loan is False
    assert result.loan_application_created is False
    assert db.execute.call_count == 2
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("mutation", [
    "legacy_source", "different_company", "different_branch",
    "different_borrower_creator", "missing_borrower_id",
    "reserved_attempt", "missing_finalize", "other_employee_attempt",
    "wrong_account_attempt", "different_branch_attempt",
])
def test_old_client_wrong_scope_or_incomplete_attempt_denied(mutation):
    ctx, account_id = staff(), uuid4()
    account, attempt = real_provenance(ctx, account_id)
    if mutation == "legacy_source":
        account.source = "assisted_registration"
    elif mutation == "different_company":
        account.company_id = uuid4()
    elif mutation == "different_branch":
        account.branch_id = uuid4()
    elif mutation == "different_borrower_creator":
        account.opened_by_user_id = uuid4()
    elif mutation == "missing_borrower_id":
        account.borrower_id = None
    elif mutation == "reserved_attempt":
        attempt.status = "reserved"
    elif mutation == "missing_finalize":
        attempt.finalized_at = None
    elif mutation == "other_employee_attempt":
        attempt.employee_user_id = uuid4()
    elif mutation == "wrong_account_attempt":
        attempt.client_account_id = uuid4()
    elif mutation == "different_branch_attempt":
        attempt.branch_id = uuid4()
    db = fake_db(account, attempt)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        assess_new_only_loan_handoff(db, context=ctx, account_id=account_id)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_no_account_or_registration_attempt_is_never_treated_as_new():
    ctx, account_id = staff(), uuid4()
    account, attempt = real_provenance(ctx, account_id)
    for missing_account, missing_attempt in [(None, attempt), (account, None)]:
        db = fake_db(missing_account, missing_attempt)
        with pytest.raises(NewOnlyLoanHandoffDenied):
            assess_new_only_loan_handoff(db, context=ctx, account_id=account_id)
        db.commit.assert_not_called()


@pytest.mark.parametrize("change", [
    "non_lending_role", "inactive_company", "revoked_employee",
    "wrong_company", "wrong_branch", "missing_branch",
])
def test_invalid_staff_or_branch_cannot_inspect_loan_handoff(change):
    ctx, account_id = staff(), uuid4()
    account, attempt = real_provenance(ctx, account_id)
    if change == "non_lending_role":
        ctx.staff.role = UserRole.AUDITOR
    elif change == "inactive_company":
        ctx.company.is_active = False
    elif change == "revoked_employee":
        ctx.staff.is_active = False
    elif change == "wrong_company":
        ctx.company.id = uuid4()
    elif change == "wrong_branch":
        ctx.staff.branch_id = uuid4()
    elif change == "missing_branch":
        object.__setattr__(ctx, "branch_id", None)
    db = fake_db(account, attempt)
    with pytest.raises((NewOnlyLoanHandoffDenied, HTTPException)):
        assess_new_only_loan_handoff(db, context=ctx, account_id=account_id)
    db.execute.assert_not_called()
    db.add.assert_not_called()


def test_no_postgresql_or_invalid_account_uuid_denied_without_writes():
    ctx, account_id = staff(), uuid4()
    account, attempt = real_provenance(ctx, account_id)
    db = fake_db(account, attempt)
    db.get_bind.return_value.dialect.name = "sqlite"
    with pytest.raises(NewOnlyLoanHandoffDenied):
        assess_new_only_loan_handoff(db, context=ctx, account_id=account_id)
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()

    db = fake_db(account, attempt)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        assess_new_only_loan_handoff(db, context=ctx, account_id="not-a-uuid")
    db.execute.assert_not_called()
