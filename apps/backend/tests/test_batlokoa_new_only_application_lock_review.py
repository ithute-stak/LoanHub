"""Offline PostgreSQL advisory-lock review remains non-writing and fail-closed."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.access_control import TenantContext
from services.batlokoa_new_only_application_lock_review import (
    NewOnlyLoanHandoffDenied,
    assess_locked_new_only_application_preflight,
)
from services.batlokoa_new_only_application_preflight import NewOnlyApplicationPreflight


def context():
    return TenantContext(
        user=SimpleNamespace(id=uuid4()),
        staff=SimpleNamespace(),
        company=None,
        company_id=uuid4(),
        branch_id=uuid4(),
        is_platform_admin=False,
    )


def preflight_result(**changes):
    base = dict(
        new_only_provenance_confirmed=True,
        product_in_company_confirmed=True,
        amount_in_product_range=True,
        term_in_product_range=True,
        no_existing_origination_applications=True,
    )
    base.update(changes)
    return NewOnlyApplicationPreflight(**base)


def database(*, acquired=True, dialect="postgresql", transaction=True):
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect),
    )
    db.in_transaction.return_value = transaction
    db.execute.return_value.scalar_one.return_value = acquired
    return db


def run(db, ctx, *, account_id=None, product_id=None, **overrides):
    return assess_locked_new_only_application_preflight(
        db, context=ctx,
        account_id=account_id if account_id is not None else uuid4(),
        product_id=product_id if product_id is not None else uuid4(),
        requested_amount=overrides.get("amount", Decimal("1200.00")),
        term_count=overrides.get("term", 4),
        request_key=overrides.get("key", "batlokoa-review-20261119-A"),
    )


def no_writes(db):
    db.add.assert_not_called()
    db.add_all.assert_not_called()
    db.delete.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_acquired_lock_checks_provenance_and_stays_nonwriting(monkeypatch):
    from services import batlokoa_new_only_application_lock_review as module
    review = MagicMock(return_value=preflight_result())
    monkeypatch.setattr(module, "assess_new_only_application_preflight", review)
    db, ctx = database(), context()
    account_id = uuid4()
    result = run(db, ctx, account_id=account_id)
    assert result.can_create_loan_application is False
    assert result.can_disburse_loan is False
    assert result.wrote_financial_records is False
    review.assert_called_once()
    statement, params = db.execute.call_args.args
    assert "pg_try_advisory_xact_lock" in str(statement)
    assert params == {
        "lock_key": "loanhub:batlokoa:new-only-application:v1:" + str(account_id)
    }
    assert "batlokoa-review-20261119-A" not in repr(params)
    no_writes(db)


@pytest.mark.parametrize("acquired", [False, None, 0, "t"])
def test_busy_or_untrusted_lock_result_denies_before_any_preflight(monkeypatch, acquired):
    from services import batlokoa_new_only_application_lock_review as module
    review = MagicMock()
    monkeypatch.setattr(module, "assess_new_only_application_preflight", review)
    db = database(acquired=acquired)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        run(db, context())
    review.assert_not_called()
    no_writes(db)


@pytest.mark.parametrize("dialect,transaction", [
    ("sqlite", True), ("postgresql", False), ("mysql", True),
])
def test_non_postgres_or_no_caller_transaction_fails_closed(monkeypatch, dialect, transaction):
    from services import batlokoa_new_only_application_lock_review as module
    review = MagicMock()
    monkeypatch.setattr(module, "assess_new_only_application_preflight", review)
    db = database(dialect=dialect, transaction=transaction)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        run(db, context())
    db.execute.assert_not_called()
    review.assert_not_called()
    no_writes(db)


@pytest.mark.parametrize("key", [
    "short", "", "spaces not allowed-123456789", "a" * 129,
    "contains\\newline--12345", "contains/forward/slash123",
])
def test_invalid_request_keys_rejected_without_a_lock(monkeypatch, key):
    from services import batlokoa_new_only_application_lock_review as module
    review = MagicMock()
    monkeypatch.setattr(module, "assess_new_only_application_preflight", review)
    db = database()
    with pytest.raises(NewOnlyLoanHandoffDenied):
        run(db, context(), key=key)
    db.execute.assert_not_called()
    review.assert_not_called()
    no_writes(db)


def test_account_lock_is_independent_of_request_key_and_product(monkeypatch):
    from services import batlokoa_new_only_application_lock_review as module
    monkeypatch.setattr(
        module, "assess_new_only_application_preflight",
        MagicMock(return_value=preflight_result()),
    )
    db, ctx, account_id = database(), context(), uuid4()
    run(db, ctx, account_id=account_id, key="batlokoa-request-key-A-123")
    first = db.execute.call_args.args[1]["lock_key"]
    run(db, ctx, account_id=account_id, key="batlokoa-request-key-B-456")
    second = db.execute.call_args.args[1]["lock_key"]
    assert first == second
    no_writes(db)


def test_even_misconfigured_preflight_result_cannot_return_write_permission(monkeypatch):
    from services import batlokoa_new_only_application_lock_review as module
    monkeypatch.setattr(
        module, "assess_new_only_application_preflight",
        MagicMock(return_value=preflight_result(can_create_loan_application=True)),
    )
    db = database()
    with pytest.raises(NewOnlyLoanHandoffDenied):
        run(db, context())
    no_writes(db)


def test_invalid_tenant_and_non_uuid_scope_rejected_prior_to_lock(monkeypatch):
    from services import batlokoa_new_only_application_lock_review as module
    review = MagicMock()
    monkeypatch.setattr(module, "assess_new_only_application_preflight", review)
    ctx = context()
    object.__setattr__(ctx, "branch_id", None)
    db = database()
    with pytest.raises(NewOnlyLoanHandoffDenied):
        run(db, ctx)
    db.execute.assert_not_called()
    review.assert_not_called()
    no_writes(db)
