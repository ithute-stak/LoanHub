"""Reject non-finite ledger values and negative source/destination balances."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.rollover_accounting_reconciliation import reconcile_rollover_accounting


@pytest.fixture
def case():
    company = uuid4()
    transfer = SimpleNamespace(
        company_id=company, principal_component=Decimal("60"),
        interest_component=Decimal("0"), fee_component=Decimal("0"),
        transfer_amount=Decimal("60"),
    )
    return dict(transfer=transfer, company_id=company,
                parent_before=Decimal("60"), parent_after=Decimal("0"),
                child_before=Decimal("0"), child_after=Decimal("60"))


def test_valid_receivable_transfer(case):
    assert reconcile_rollover_accounting(**case)["balanced"] is True


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "not-a-number", None])
@pytest.mark.parametrize("field", ["transfer_amount", "principal_component"])
def test_invalid_ledger_value_fails_closed(case, field, value):
    setattr(case["transfer"], field, value)
    with pytest.raises(HTTPException) as exc:
        reconcile_rollover_accounting(**case)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("field", ["parent_before", "parent_after", "child_before", "child_after"])
@pytest.mark.parametrize("value", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), "broken"])
def test_invalid_or_negative_receivable_fails_closed(case, field, value):
    case[field] = value
    with pytest.raises(HTTPException) as exc:
        reconcile_rollover_accounting(**case)
    assert exc.value.status_code == 409


def test_reverse_transfer_is_balanced_with_swapped_roles(case):
    case.update(parent_before=Decimal("60"), parent_after=Decimal("0"),
                child_before=Decimal("0"), child_after=Decimal("60"))
    assert reconcile_rollover_accounting(**case)["company_gl_net_change"] == "0.00"
