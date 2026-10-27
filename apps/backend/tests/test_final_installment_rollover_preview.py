"""Final-installment proposal must never silently originate fresh credit."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus, RepaymentType
from services.final_installment_rollover_preview import preview_final_installment_rollover


def make_loan(*, paid="99.31", total="100.00"):
    installment = SimpleNamespace(
        id=uuid4(), installment_number=3, is_superseded=False,
        status=InstallmentStatus.PARTIALLY_PAID,
        total_due=Decimal(total), paid_amount=Decimal(paid),
    )
    loan = SimpleNamespace(
        id=uuid4(), borrower_id=uuid4(), company_id=uuid4(), branch_id=None,
        status=LoanStatus.ACTIVE, balance=Decimal("0.69"),
        installments=[installment], repayment_type=RepaymentType.MONTHLY,
        interest_rate=Decimal("20"), calculation_method="micro_loan",
        cdas_collection_enabled=False,
    )
    return loan, installment


def test_preview_inherits_parent_but_does_not_post_cash_or_credit():
    loan, installment = make_loan()
    report = preview_final_installment_rollover(loan, installment.id)
    assert report["unpaid_remainder"] == "0.69"
    assert report["proposed_child_principal"] == "0.69"
    assert report["proposed_cash_disbursement"] == "0.00"
    assert report["ready_to_post"] is False
    assert report["requires_credit_approval"] is True
    assert report["requires_signed_amendment"] is True


def test_fully_unpaid_final_installment_not_eligible():
    loan, installment = make_loan(paid="0")
    with pytest.raises(HTTPException) as exc:
        preview_final_installment_rollover(loan, installment.id)
    assert exc.value.status_code == 409
