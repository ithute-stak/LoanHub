"""Exercise cancellation behavior with an isolated mocked database: no live writes."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import LoanStatus, UserRole
from routers import loans


def _scenario(monkeypatch, *, has_payment=False):
    monkeypatch.setattr(loans, "require_tenant_roles", lambda *args: None)
    monkeypatch.setattr(loans, "assert_branch_scope", lambda *args: None)

    company_id, branch_id, loan_id = uuid4(), uuid4(), uuid4()
    user_id = uuid4()
    loan = SimpleNamespace(
        id=loan_id, company_id=company_id, branch_id=branch_id,
        loan_reference="UNIT-TEST-LOAN", status=LoanStatus.APPROVED,
        disbursed_at=None, disbursed_by_user_id=None,
        amount_paid=Decimal("0"), balance=Decimal("1000"),
        total_repayable=Decimal("1200"), installments=[],
    )
    contract = SimpleNamespace(
        id=uuid4(), status="signed", contract_hash="frozen-hash",
        borrower_signed_at="borrower-signed", company_signed_at="company-signed",
        pdf_file_id=uuid4(), locked_at="signed-and-locked",
    )
    application = SimpleNamespace(status="approved", decision_notes="Decision approved")
    db = MagicMock()
    rows = [loan, object() if has_payment else None, None, None, None, contract, application]
    query_index = iter(rows)

    def fake_query(*args, **kwargs):
        value = next(query_index)
        query = MagicMock()
        query.filter.return_value = query
        query.with_for_update.return_value = query
        query.first.return_value = value
        return query

    db.query.side_effect = fake_query
    context = SimpleNamespace(
        company_id=company_id, role=UserRole.COMPANY_OWNER,
        user=SimpleNamespace(id=user_id),
    )
    payload = loans.CancelUndisbursedLoanRequest(
        reason="Facility withdrawn by mutual agreement",
        signed_termination_reference="TERM-UNIT-001",
        confirm_no_disbursement=True,
    )
    return db, loan, contract, application, payload, context


def test_cancellation_executes_and_preserves_original_signed_document(monkeypatch):
    db, loan, contract, application, payload, context = _scenario(monkeypatch)
    original = (
        contract.status, contract.contract_hash, contract.pdf_file_id,
        contract.borrower_signed_at, contract.company_signed_at, contract.locked_at,
        loan.balance, loan.total_repayable,
    )

    result = loans.cancel_approved_undisbursed_loan(
        loan.id, payload, db=db, context=context,
    )

    assert result is loan
    assert loan.status == LoanStatus.CANCELLED
    assert application.status == "cancelled"
    assert application.decision_notes.startswith("Decision approved")
    assert (
        contract.status, contract.contract_hash, contract.pdf_file_id,
        contract.borrower_signed_at, contract.company_signed_at, contract.locked_at,
        loan.balance, loan.total_repayable,
    ) == original
    db.commit.assert_called_once()
    audit_events = [call.args[0] for call in db.add.call_args_list]
    assert len(audit_events) == 1
    assert audit_events[0].action == "loan.approved_undisbursed_cancelled"
    assert audit_events[0].event_data["contract_hash"] == "frozen-hash"


def test_cancellation_refuses_payment_activity_without_changing_loan(monkeypatch):
    db, loan, contract, application, payload, context = _scenario(
        monkeypatch, has_payment=True,
    )
    with pytest.raises(HTTPException) as error:
        loans.cancel_approved_undisbursed_loan(
            loan.id, payload, db=db, context=context,
        )

    assert error.value.status_code == 409
    assert loan.status == LoanStatus.APPROVED
    assert contract.status == "signed"
    assert application.status == "approved"
    db.commit.assert_not_called()
    db.add.assert_not_called()
