"""Rollover compensation must reject reclassification of the child debt."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.rollover_reversal_preflight import validate_rollover_reversal_preflight


def fixture_data():
    company, parent_id, child_id, transfer_id = (uuid4() for _ in range(4))
    parent = SimpleNamespace(
        id=parent_id, company_id=company, balance=Decimal("0"),
        calculation_breakdown={"linked_rollover_out": {
            "child_loan_id": str(child_id), "amount": "60",
        }},
    )
    child = SimpleNamespace(
        id=child_id, company_id=company, parent_loan_id=parent_id,
        amount_paid=Decimal("0"), balance=Decimal("60"), status="active",
    )
    transfer = SimpleNamespace(
        id=transfer_id, company_id=company, parent_loan_id=parent_id,
        child_loan_id=child_id, status="posted", transfer_amount=Decimal("60"),
        principal_component=Decimal("40"), interest_component=Decimal("15"),
        fee_component=Decimal("5"),
    )
    installment = SimpleNamespace(
        is_superseded=False, paid_amount=Decimal("0"),
        total_due=Decimal("60"), principal_due=Decimal("40"),
        interest_due=Decimal("15"), fee_due=Decimal("5"),
    )
    return dict(
        transfer=transfer, parent=parent, child=child,
        child_installments=[installment], child_payments_count=0,
        actor_company_id=company,
    )


def test_unchanged_child_components_can_pass_readonly_preflight():
    assert validate_rollover_reversal_preflight(**fixture_data())[
        "eligible_for_manual_review"
    ] is True


@pytest.mark.parametrize("principal,interest,fees", [
    ("45", "10", "5"),
    ("40", "20", "0"),
    ("35", "15", "10"),
])
def test_reclassified_components_are_rejected_even_when_total_unchanged(
    principal, interest, fees,
):
    data = fixture_data()
    row = data["child_installments"][0]
    row.principal_due = Decimal(principal)
    row.interest_due = Decimal(interest)
    row.fee_due = Decimal(fees)
    assert row.principal_due + row.interest_due + row.fee_due == Decimal("60")
    with pytest.raises(HTTPException) as error:
        validate_rollover_reversal_preflight(**data)
    assert error.value.status_code == 409
