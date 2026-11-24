"""Read-only company policy loading tests.

These tests use a fake query to ensure the loader does not write or
implicitly activate the Principal x% model.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from payment_engine.principal_x_policy import PaymentModel
from services.company_payment_model_settings_service import read_company_payment_policy


class Query:
    def __init__(self, row):
        self.row = row
        self.filters = []

    def filter(self, predicate):
        self.filters.append(predicate)
        return self

    def one_or_none(self):
        return self.row


class Database:
    def __init__(self, row):
        self.query_result = Query(row)
        self.queried_models = []

    def query(self, model):
        self.queried_models.append(model)
        return self.query_result


def test_absent_company_settings_do_not_enable_new_payment_model():
    db = Database(None)
    policy = read_company_payment_policy(db, company_id=str(uuid4())).as_policy()
    assert policy.company_default == PaymentModel.EXISTING
    assert not policy.allow_new_loans
    assert not policy.enable_live_collections
    assert len(db.query_result.filters) == 1


def test_company_explicit_settings_are_read_without_mutation():
    row = SimpleNamespace(
        default_model="principal_x",
        allow_new_loans=True,
        enable_live_collections=False,
    )
    db = Database(row)
    policy = read_company_payment_policy(db, company_id=str(uuid4())).as_policy()
    assert policy.company_default == PaymentModel.PRINCIPAL_X
    assert policy.allow_new_loans
    assert not policy.enable_live_collections


def test_invalid_persisted_company_settings_fail_closed():
    db = Database(SimpleNamespace(
        default_model="principal_x",
        allow_new_loans="true",
        enable_live_collections=False,
    ))
    with pytest.raises(ValueError, match="boolean"):
        read_company_payment_policy(db, company_id=str(uuid4()))


def test_company_identity_required():
    with pytest.raises(ValueError, match="Company ID"):
        read_company_payment_policy(Database(None), company_id="")
