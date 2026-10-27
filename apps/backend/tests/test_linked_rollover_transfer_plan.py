"""Rollover ledger transfer plan safety: no extra receivable, fee or cash."""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus, RepaymentType
from services.linked_rollover_transfer_plan import prepare_linked_rollover


def sample():
    row = SimpleNamespace(
        id=uuid4(), installment_number=1, is_superseded=False,
        status=InstallmentStatus.PARTIALLY_PAID,
        total_due=Decimal("100"), paid_amount=Decimal("99.31"),
    )
    loan = SimpleNamespace(
        id=uuid4(), borrower_id=uuid4(), company_id=uuid4(), branch_id=None,
        status=LoanStatus.ACTIVE, balance=Decimal("0.69"), installments=[row],
        repayment_type=RepaymentType.MONTHLY, interest_rate=Decimal("15"),
        calculation_method="micro_loan", cdas_collection_enabled=False,
        is_top_up=False, renewal_cycle_count=0,
    )
    return loan, row


def plan(loan, row, **kw):
    args = dict(
        approved_amount=Decimal("0.69"),
        effective_due_date=date.today() + timedelta(days=30),
        agreement_reference="SIGNED-2026", approval_reference="APPROVED-2026",
        as_of=date.today(),
    )
    args.update(kw)
    return prepare_linked_rollover(loan, row.id, **args)


def test_transfer_plan_preserves_total_receivable_without_phantom_cash():
    loan, row = sample()
    result = plan(loan, row)
    assert result["total_receivable_before"] == result["total_receivable_after"] == "0.69"
    assert result["new_cash_disbursement"] == result["new_interest_or_fee"] == "0.00"
    assert result["posting_enabled"] is False
    assert loan.balance == Decimal("0.69")


@pytest.mark.parametrize("changes", [
    {"approved_amount": Decimal("0.70")},
    {"agreement_reference": ""},
    {"approval_reference": ""},
    {"effective_due_date": date.today()},
])
def test_unreconciled_or_unapproved_transfer_rejected(changes):
    loan, row = sample()
    with pytest.raises(HTTPException):
        plan(loan, row, **changes)


def test_prior_maturity_renewal_rejected():
    loan, row = sample()
    loan.renewal_cycle_count = 1
    with pytest.raises(HTTPException):
        plan(loan, row)
