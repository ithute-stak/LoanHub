from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.loan_service import _require_signed_contract_before_disbursement


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.value


class _Db:
    def __init__(self, *, policy=None, contract=None):
        self.policy = policy
        self.contract = contract

    def query(self, model):
        if model.__name__ == "OriginationPolicy":
            return _Query(self.policy)
        if model.__name__ == "LoanContract":
            return _Query(self.contract)
        raise AssertionError(f"Unexpected model query: {model}")


def _loan():
    return SimpleNamespace(id=uuid4(), company_id=uuid4())


def test_online_loan_without_contract_is_blocked_by_secure_default():
    with pytest.raises(HTTPException) as caught:
        _require_signed_contract_before_disbursement(_Db(), _loan())
    assert caught.value.status_code == 409
    assert "Generate the loan contract" in str(caught.value.detail)


def test_online_loan_with_partial_signatures_is_blocked():
    contract = SimpleNamespace(
        status="borrower_signed",
        borrower_signed_at=object(),
        company_signed_at=None,
    )
    with pytest.raises(HTTPException) as caught:
        _require_signed_contract_before_disbursement(
            _Db(policy=SimpleNamespace(require_signed_contract=True), contract=contract),
            _loan(),
        )
    assert caught.value.status_code == 409
    assert "company" in str(caught.value.detail)


def test_fully_signed_online_loan_can_pass_contract_gate():
    contract = SimpleNamespace(
        status="signed",
        borrower_signed_at=object(),
        company_signed_at=object(),
    )
    assert (
        _require_signed_contract_before_disbursement(
            _Db(policy=SimpleNamespace(require_signed_contract=True), contract=contract),
            _loan(),
        )
        is contract
    )


def test_explicit_policy_can_disable_contract_gate():
    assert (
        _require_signed_contract_before_disbursement(
            _Db(policy=SimpleNamespace(require_signed_contract=False)),
            _loan(),
        )
        is None
    )


def test_contract_service_uses_online_request_and_offer_metadata():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "services" / "contract_service.py").read_text(encoding="utf-8")
    assert "online_request = db.get(LoanRequest, loan.loan_request_id)" in source
    assert "accepted_offer = db.get(LoanOffer, loan.loan_offer_id)" in source
    assert '"origination_channel": loan.origination_channel' in source


def test_company_ui_never_enables_disbursement_without_signed_contract():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    source = (frontend / "app" / "(dashboard)" / "company" / "loans" / "page.tsx").read_text(encoding="utf-8")
    assert 'contract?.status === "signed"' in source
    assert "Sign contract first" in source
    assert "Fully signed contract required" in source
