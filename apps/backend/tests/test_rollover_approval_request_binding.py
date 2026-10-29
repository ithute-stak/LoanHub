"""Reversal approval is valid only for its authenticated maker request."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import rollover_reversal_approval as service


class FakeQuery:
    def __init__(self, value):
        self.value = value
    def filter(self, *args):
        return self
    def one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, decision, request):
        self.decision, self.request = decision, request
    def query(self, model):
        if model is service.LoanRolloverReversalApproval:
            return FakeQuery(self.decision)
        if model is service.LoanRolloverReversalRequest:
            return FakeQuery(self.request)
        raise AssertionError("Unexpected query")


@pytest.mark.parametrize("case", ["valid", "missing_request", "wrong_request_id", "missing_evidence"])
def test_approval_must_match_authenticated_maker_request(monkeypatch, case):
    company, transfer, maker, checker, request_id = (uuid4() for _ in range(5))
    request = SimpleNamespace(id=request_id)
    evidence = {"maker_request_id": str(request_id)}
    if case == "missing_request":
        request = None
    elif case == "wrong_request_id":
        evidence["maker_request_id"] = str(uuid4())
    elif case == "missing_evidence":
        evidence = {}
    decision = SimpleNamespace(evidence=evidence)
    checked = []
    monkeypatch.setattr(service, "verify_rollover_checker_identity", lambda *args, **kwargs: checked.append(kwargs))
    db = FakeDB(decision, request)
    args = dict(company_id=company, transfer_id=transfer,
                maker_user_id=maker, checker_user_id=checker,
                approval_reference="REV-APPROVED")
    if case == "valid":
        assert service.require_rollover_reversal_approval(db, **args) is decision
        assert len(checked) == 1
    else:
        with pytest.raises(HTTPException) as exc:
            service.require_rollover_reversal_approval(db, **args)
        assert exc.value.status_code == 409
        assert not checked
