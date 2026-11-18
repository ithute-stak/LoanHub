from types import SimpleNamespace
from uuid import uuid4

import pytest

from payment_engine.principal_x_policy import PaymentModel, PaymentModelPolicy
from services.loan_payment_model_assignment_writer import create_loan_payment_model_assignment


class Query:
    def __init__(self, existing=None):
        self.existing = existing

    def filter(self, *predicates):
        return self

    def one_or_none(self):
        return self.existing


class Database:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    def query(self, model):
        return Query(self.existing)

    def add(self, record):
        self.added.append(record)


def make_loan(company_id=None, **changes):
    values = dict(id=uuid4(), company_id=company_id or uuid4(),
                  approved_at=None, disbursed_at=None)
    values.update(changes)
    return SimpleNamespace(**values)


def test_new_loan_assignment_is_written_without_commit():
    loan = make_loan()
    db = Database()
    row = create_loan_payment_model_assignment(
        db, loan=loan, company_id=loan.company_id,
        policy=PaymentModelPolicy(PaymentModel.PRINCIPAL_X, True, False),
    )
    assert row.payment_model == "principal_x"
    assert db.added == [row]


def test_duplicate_assignment_is_rejected():
    loan = make_loan()
    with pytest.raises(ValueError, match="already"):
        create_loan_payment_model_assignment(
            Database(existing=object()), loan=loan,
            company_id=loan.company_id, policy=PaymentModelPolicy(),
        )


def test_cross_company_assignment_is_rejected():
    loan = make_loan()
    with pytest.raises(ValueError, match="different company"):
        create_loan_payment_model_assignment(
            Database(), loan=loan, company_id=uuid4(),
            policy=PaymentModelPolicy(),
        )


@pytest.mark.parametrize("field", ["approved_at", "disbursed_at"])
def test_post_approval_or_disbursement_assignment_rejected(field):
    loan = make_loan(**{field: object()})
    with pytest.raises(ValueError, match="cannot receive"):
        create_loan_payment_model_assignment(
            Database(), loan=loan, company_id=loan.company_id,
            policy=PaymentModelPolicy(),
        )


def test_company_opt_in_required():
    loan = make_loan()
    with pytest.raises(ValueError, match="not enabled"):
        create_loan_payment_model_assignment(
            Database(), loan=loan, company_id=loan.company_id,
            policy=PaymentModelPolicy(),
            requested_model=PaymentModel.PRINCIPAL_X,
        )
