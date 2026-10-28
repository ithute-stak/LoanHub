"""Conservation tests for intra-company rollover accounting policy."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from services.rollover_accounting_reconciliation import reconcile_rollover_accounting


def transfer(company, principal="60", interest="20", fee="10", total="90"):
    return SimpleNamespace(company_id=company, principal_component=principal,
                           interest_component=interest, fee_component=fee,
                           transfer_amount=total)


def run(t, company, before="90", after="0", child_before="0", child_after="90"):
    return reconcile_rollover_accounting(
        transfer=t, company_id=company, parent_before=before,
        parent_after=after, child_before=child_before, child_after=child_after,
    )


def test_intra_company_transfer_preserves_gl_balances():
    company = uuid4()
    result = run(transfer(company), company)
    assert result["balanced"] is True
    assert result["company_gl_net_change"] == "0.00"
    assert result["no_cash_movement"] and result["no_new_income"]
    assert result["component_accounts"] == {
        "principal": "1100", "interest": "1110", "fees": "1120"
    }
    assert result["posting_enabled"] is False


@pytest.mark.parametrize("values", [
    {"total": "91"}, {"principal": "-1"}, {"after": "10"},
    {"child_after": "80"}, {"child_before": "10"},
])
def test_invalid_movements_fail_closed(values):
    company = uuid4()
    components = {k: v for k, v in values.items() if k in {"principal", "interest", "fee", "total"}}
    movement = {k: v for k, v in values.items() if k not in components}
    with pytest.raises(HTTPException) as exc:
        run(transfer(company, **components), company, **movement)
    assert exc.value.status_code == 409


def test_cross_company_transfer_hidden():
    with pytest.raises(HTTPException) as exc:
        run(transfer(uuid4()), uuid4())
    assert exc.value.status_code == 404
