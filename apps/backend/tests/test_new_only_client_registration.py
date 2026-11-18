"""Phase 68 tests: no registration writes, no legacy borrower linkage."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel
from core.access_control import TenantContext
from database.models.enums import UserRole

from services.new_only_client_registration import (
    NewOnlyRegistrationNotReady, execute_new_only_registration,
    prepare_new_only_registration_intent,
)


class SyntheticRequest(BaseModel):
    first_name: str = "Palesa"
    last_name: str = "Mokoena"
    phone: str = "59000000"
    date_of_birth: date = date(1990, 2, 1)
    national_id: str | None = "SYNTH-ID"
    passport_number: str | None = None
    monthly_income: str = "4500.00"
    consent_to_credit_checks: bool = False


def context():
    company, branch, actor = uuid4(), uuid4(), uuid4()
    return TenantContext(
        company_id=company,
        user=SimpleNamespace(id=actor, is_active=True),
        branch_id=branch,
        staff=SimpleNamespace(
            user_id=actor, company_id=company, branch_id=branch,
            role=UserRole.LOAN_OFFICER, is_active=True,
        ),
        company=None,
        is_platform_admin=False,
    )

def prepare(ctx, payload=None, **kwargs):
    with patch("services.new_only_client_registration.require_tenant_roles"), patch(
        "services.new_only_client_registration.assert_branch_scope"
    ):
        return prepare_new_only_registration_intent(
            context=ctx, branch_id=ctx.branch_id,
            idempotency_key="employee-client-request-0001",
            payload=payload or SyntheticRequest(),
            secret=b"synthetic-test-secret-with-at-least-32-bytes",
            **kwargs,
        )


def test_intent_is_bound_to_employee_tenant_and_branch():
    ctx = context()
    result = prepare(ctx)
    assert result.company_id == ctx.company_id
    assert result.employee_id == ctx.user.id
    assert result.branch_id == ctx.branch_id
    assert len(result.registration_fingerprint) == 64
    assert "SYNTH-ID" not in str(result)
    assert "59000000" not in str(result)


def test_any_financial_or_consent_change_invalidates_replay_fingerprint():
    ctx = context()
    first = prepare(ctx, SyntheticRequest())
    changed_income = prepare(ctx, SyntheticRequest(monthly_income="4800.00"))
    changed_consent = prepare(ctx, SyntheticRequest(consent_to_credit_checks=True))
    assert first.registration_fingerprint != changed_income.registration_fingerprint
    assert first.registration_fingerprint != changed_consent.registration_fingerprint


def test_wrong_key_or_secret_refused():
    ctx = context()
    with pytest.raises(ValueError):
        with patch("services.new_only_client_registration.require_tenant_roles"), patch(
            "services.new_only_client_registration.assert_branch_scope"
        ):
            prepare_new_only_registration_intent(
                context=ctx, branch_id=ctx.branch_id,
                idempotency_key="x", payload=SyntheticRequest(),
                secret=b"short",
            )


def test_execution_always_rejects_after_read_only_lock_and_guard():
    db = MagicMock()
    intent = prepare(context())
    with patch(
        "services.new_only_client_registration.check_with_transaction_identity_locks"
    ) as guard:
        with pytest.raises(NewOnlyRegistrationNotReady):
            execute_new_only_registration(
                db, intent=intent, national_id="SYNTH-ID",
                passport_number=None, phone="59000000")
    assert guard.call_count == 1
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_unverified_intent_does_not_reach_database():
    db = MagicMock()
    with pytest.raises(NewOnlyRegistrationNotReady):
        execute_new_only_registration(
            db, intent=None, national_id="SYNTH-ID",
            passport_number=None, phone="59000000")
    db.execute.assert_not_called()


@pytest.mark.parametrize("change", [
    {"is_platform_admin": True},
    {"staff_active": False},
    {"user_active": False},
    {"branch_id": None},
    {"wrong_company": True},
    {"wrong_actor": True},
])
def test_untrusted_or_inactive_staff_cannot_prepare_intent(change):
    from dataclasses import replace
    ctx = context()
    if "is_platform_admin" in change:
        ctx = replace(ctx, is_platform_admin=True)
    if "staff_active" in change:
        ctx.staff.is_active = False
    if "user_active" in change:
        ctx.user.is_active = False
    if "branch_id" in change:
        ctx = replace(ctx, branch_id=None)
    if "wrong_company" in change:
        ctx.staff.company_id = uuid4()
    if "wrong_actor" in change:
        ctx.staff.user_id = uuid4()
    with pytest.raises(ValueError):
        prepare(ctx)


def test_manager_may_prepare_for_different_branch_if_membership_valid():
    from dataclasses import replace
    ctx = context()
    ctx.staff.role = UserRole.COMPANY_ADMIN
    selected_branch = uuid4()
    with patch("services.new_only_client_registration.require_tenant_roles"), patch(
        "services.new_only_client_registration.assert_branch_scope"
    ):
        result = prepare_new_only_registration_intent(
            context=ctx, branch_id=selected_branch,
            idempotency_key="employee-client-request-0001",
            payload=SyntheticRequest(),
            secret=b"synthetic-test-secret-with-at-least-32-bytes",
        )
    assert result.branch_id == selected_branch
