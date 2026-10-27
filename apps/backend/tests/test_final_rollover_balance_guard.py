"""Linked rollover preview requires a completely reconciled remaining parent balance."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import InstallmentStatus, LoanStatus, RepaymentType
from services.final_installment_rollover_preview import preview_final_installment_rollover


def test_final_shortfall_does_not_create_duplicate_debt_when_other_balance_remains():
    final = SimpleNamespace(
        id=uuid4(), installment_number=3, is_superseded=False,
        status=InstallmentStatus.PARTIALLY_PAID, total_due=Decimal("100.00"), paid_amount=Decimal("99.31"),
    )
    loan = SimpleNamespace(
        id=uuid4(), borrower_id=uuid4(), company_id=uuid4(), branch_id=None,
        status=LoanStatus.ACTIVE, balance=Decimal("10.69"),
        installments=[final], repayment_type=RepaymentType.MONTHLY,
        interest_rate=Decimal("20"), calculation_method="micro_loan",
        cdas_collection_enabled=False,
    )
    with pytest.raises(HTTPException) as raised:
        preview_final_installment_rollover(loan, final.id)
    assert raised.value.status_code == 409


def test_final_rollover_preview_is_available_from_loan_schedule():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[3] / "apps/frontend/app/(dashboard)/company/loans/page.tsx").read_text()
    assert "Preview final rollover" in page
    assert "previewFinalRollover(item)" in page
    assert "No loan or financial posting has been created." in page
