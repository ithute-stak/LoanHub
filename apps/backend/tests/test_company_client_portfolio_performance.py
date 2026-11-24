"""Regression coverage for the lightweight client-portfolio insights query path."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from routers.company_clients import (
    BorrowerBankAccount,
    ClientCompanyLoan,
    CompanyClientCaseEntry,
    RepaymentInstallment,
    _directory_summaries,
)


def test_portfolio_insights_skips_unneeded_bank_and_case_queries():
    borrower_id, loan_id, account_id, company_id = (uuid4() for _ in range(4))
    accounts = [SimpleNamespace(id=account_id, borrower_id=borrower_id)]
    loans = [SimpleNamespace(id=loan_id, borrower_id=borrower_id)]
    installments = [SimpleNamespace(loan_id=loan_id)]
    db = MagicMock()
    queried_models = []

    def query(model):
        queried_models.append(model)
        chain = MagicMock()
        if model is ClientCompanyLoan:
            chain.filter.return_value.order_by.return_value.all.return_value = loans
        elif model is RepaymentInstallment:
            chain.filter.return_value.all.return_value = installments
        else:
            raise AssertionError(f"Unexpected expensive query: {model}")
        return chain

    db.query.side_effect = query
    summary, returned_loans, returned_installments = _directory_summaries(
        db,
        context=SimpleNamespace(company_id=company_id),
        accounts=accounts,
        include_summaries=False,
    )
    assert summary == {}
    assert returned_loans is loans
    assert returned_installments is installments
    assert queried_models == [ClientCompanyLoan, RepaymentInstallment]
    assert BorrowerBankAccount not in queried_models
    assert CompanyClientCaseEntry not in queried_models


def test_empty_portfolio_does_not_issue_queries():
    db = MagicMock()
    result = _directory_summaries(
        db,
        context=SimpleNamespace(company_id=uuid4()),
        accounts=[],
        include_summaries=False,
    )
    assert result == ({}, [], [])
    db.query.assert_not_called()
