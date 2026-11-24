"""Offline new-only application preflight rejects duplicate and unsafe products."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.access_control import TenantContext
from database.models.enums import CompanyStatus, UserRole
from services.batlokoa_new_only_application_preflight import (
    NewOnlyLoanHandoffDenied,
    assess_new_only_application_preflight,
)


def context():
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


def setup(monkeypatch):
    from services import batlokoa_new_only_application_preflight as module
    # The provenance verifier has its own regression tests. Here it is
    # replaced only to isolate the product and duplicate query boundary.
    provenance = MagicMock()
    monkeypatch.setattr(module, "assess_new_only_loan_handoff", provenance)
    ctx, account_id, product_id, borrower_id = context(), uuid4(), uuid4(), uuid4()
    account = SimpleNamespace(
        id=account_id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        borrower_id=borrower_id, source="new_only_registration",
        opened_by_user_id=ctx.user.id,
    )
    product = SimpleNamespace(
        id=product_id, company_id=ctx.company_id, is_active=True,
        min_amount=Decimal("100.00"), max_amount=Decimal("10000.00"),
        min_term_months=1, max_term_months=12,
    )
    db = MagicMock()
    def results(existing=None):
        db.execute.return_value.scalar_one_or_none.side_effect = [
            account, product, existing,
        ]
    results()
    return ctx, db, account, product, account_id, product_id, provenance, results


def invoke(ctx, db, account_id, product_id, **kwargs):
    return assess_new_only_application_preflight(
        db,
        context=ctx,
        account_id=account_id,
        product_id=product_id,
        requested_amount=kwargs.get("requested_amount", Decimal("1000.00")),
        term_count=kwargs.get("term_count", 3),
    )


def assert_no_mutations(db):
    db.add.assert_not_called()
    db.add_all.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_valid_scoped_product_and_no_existing_application_still_cannot_create_loan(monkeypatch):
    ctx, db, account, product, account_id, product_id, provenance, _ = setup(monkeypatch)
    r = invoke(ctx, db, account_id, product_id)
    assert r.new_only_provenance_confirmed is True
    assert r.product_in_company_confirmed is True
    assert r.no_existing_origination_applications is True
    assert r.requires_affordability_assessment is True
    assert r.requires_underwriting_and_credit_approval is True
    assert r.requires_identity_and_kyc_review is True
    assert r.can_create_loan_application is False
    assert r.can_disburse_loan is False
    assert r.wrote_financial_records is False
    provenance.assert_called_once()
    assert db.execute.call_count == 3
    assert_no_mutations(db)


@pytest.mark.parametrize("attribute,new_value", [
    ("company_id", "different_company"),
    ("is_active", False),
    ("min_amount", Decimal("1200.00")),
    ("max_amount", Decimal("900.00")),
    ("max_term_months", 2),
    ("min_term_months", 4),
])
def test_wrong_product_or_out_of_range_terms_denied(monkeypatch, attribute, new_value):
    ctx, db, account, product, account_id, product_id, _, _ = setup(monkeypatch)
    setattr(product, attribute, uuid4() if new_value == "different_company" else new_value)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        invoke(ctx, db, account_id, product_id)
    assert_no_mutations(db)


@pytest.mark.parametrize("field", [
    "company_id", "branch_id", "opened_by_user_id", "source", "borrower_id",
])
def test_account_scope_mismatch_denied(monkeypatch, field):
    ctx, db, account, product, account_id, product_id, _, _ = setup(monkeypatch)
    setattr(account, field, "assisted_registration" if field == "source" else uuid4())
    with pytest.raises(NewOnlyLoanHandoffDenied):
        invoke(ctx, db, account_id, product_id)
    assert db.execute.call_count == 1
    assert_no_mutations(db)


@pytest.mark.parametrize("amount,term", [
    (Decimal("0"), 3), (Decimal("-1"), 3),
    (Decimal("NaN"), 3), (Decimal("Infinity"), 3),
    (Decimal("1000.001"), 3), ("1000", 3),
    (Decimal("1000"), 0), (Decimal("1000"), 121),
    (Decimal("1000"), True),
])
def test_invalid_money_or_term_denied_without_queries(monkeypatch, amount, term):
    ctx, db, _, _, account_id, product_id, provenance, _ = setup(monkeypatch)
    with pytest.raises(NewOnlyLoanHandoffDenied):
        invoke(ctx, db, account_id, product_id, requested_amount=amount, term_count=term)
    provenance.assert_called_once()
    db.execute.assert_not_called()
    assert_no_mutations(db)


def test_any_prior_origination_application_blocks_handoff(monkeypatch):
    ctx, db, account, product, account_id, product_id, _, results = setup(monkeypatch)
    results(existing=uuid4())
    with pytest.raises(NewOnlyLoanHandoffDenied, match="Existing origination"):
        invoke(ctx, db, account_id, product_id)
    assert_no_mutations(db)


def test_missing_account_or_product_blocks_handoff(monkeypatch):
    ctx, db, account, product, account_id, product_id, _, _ = setup(monkeypatch)
    for sequence in ([None], [account, None]):
        db.reset_mock()
        db.execute.return_value.scalar_one_or_none.side_effect = sequence
        with pytest.raises(NewOnlyLoanHandoffDenied):
            invoke(ctx, db, account_id, product_id)
        assert_no_mutations(db)
