from types import SimpleNamespace
from uuid import uuid4

import pytest

from payment_engine.principal_x_policy import PaymentModel
from services.loan_payment_model_assignment_service import read_loan_payment_model


class Query:
    def __init__(self, record):
        self.record = record
        self.predicates = ()

    def filter(self, *predicates):
        self.predicates = predicates
        return self

    def one_or_none(self):
        return self.record


class Database:
    def __init__(self, record):
        self.result = Query(record)

    def query(self, model):
        return self.result


def test_historical_loan_without_assignment_uses_existing_model():
    db = Database(None)
    result = read_loan_payment_model(
        db, loan_id=str(uuid4()), company_id=str(uuid4()),
    )
    assert result == PaymentModel.EXISTING
    assert len(db.result.predicates) == 2


def test_explicit_assignment_is_preserved():
    db = Database(SimpleNamespace(payment_model="principal_x"))
    assert read_loan_payment_model(
        db, loan_id=str(uuid4()), company_id=str(uuid4()),
    ) == PaymentModel.PRINCIPAL_X


def test_unknown_assignment_fails_closed():
    db = Database(SimpleNamespace(payment_model="unsupported"))
    with pytest.raises(ValueError, match="Unknown"):
        read_loan_payment_model(
            db, loan_id=str(uuid4()), company_id=str(uuid4()),
        )


@pytest.mark.parametrize("loan_id,company_id", [("", "company"), ("loan", "")])
def test_both_identifiers_are_required(loan_id, company_id):
    with pytest.raises(ValueError, match="identity"):
        read_loan_payment_model(
            Database(None), loan_id=loan_id, company_id=company_id,
        )
