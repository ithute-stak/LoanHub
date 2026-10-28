from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from services.rollover_reversal_preflight import validate_rollover_reversal_preflight


def sample():
    company,parent_id,child_id=uuid4(),uuid4(),uuid4()
    transfer=SimpleNamespace(id=uuid4(),company_id=company,parent_loan_id=parent_id,child_loan_id=child_id,status="posted",transfer_amount=Decimal("20.00"))
    parent=SimpleNamespace(id=parent_id,company_id=company,balance=Decimal("0"),calculation_breakdown={"linked_rollover_out":{"child_loan_id":str(child_id),"amount":"20.00"}})
    child=SimpleNamespace(id=child_id,parent_loan_id=parent_id,company_id=company,balance=Decimal("20.00"),amount_paid=Decimal("0"),status="active")
    installments=[SimpleNamespace(paid_amount=Decimal("0"),total_due=Decimal("20.00"),is_superseded=False)]
    return dict(transfer=transfer,parent=parent,child=child,child_installments=installments,child_payments_count=0,actor_company_id=company)


def test_unmodified_rollover_can_only_be_reviewed_not_posted():
    result=validate_rollover_reversal_preflight(**sample())
    assert result["eligible_for_manual_review"]
    assert result["posting_enabled"] is False
    assert result["requires_compensating_journal"]


@pytest.mark.parametrize("mutation", [
    lambda x: setattr(x["child"],"amount_paid",Decimal("1")),
    lambda x: setattr(x["child"],"balance",Decimal("19")),
    lambda x: setattr(x["parent"],"balance",Decimal("20")),
    lambda x: setattr(x["transfer"],"status","reversed"),
    lambda x: x.update(child_payments_count=1),
    lambda x: x.update(actor_company_id=uuid4()),
    lambda x: x["child_installments"].append(SimpleNamespace(paid_amount=0,total_due=20)),
])
def test_changed_or_cross_tenant_rollover_rejected(mutation):
    args=sample()
    mutation(args)
    with pytest.raises(HTTPException) as exc:
        validate_rollover_reversal_preflight(**args)
    assert exc.value.status_code in (404,409)


def test_inactive_child_and_superseded_schedule_rejected():
    for change in ("inactive", "superseded"):
        args = sample()
        if change == "inactive":
            args["child"].status = "cancelled"
        else:
            args["child_installments"][0].is_superseded = True
        with pytest.raises(HTTPException) as exc:
            validate_rollover_reversal_preflight(**args)
        assert exc.value.status_code == 409
