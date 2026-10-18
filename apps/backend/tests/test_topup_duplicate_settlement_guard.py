"""Executable regression tests for top-up settlement replay protection."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.loan_service import _reject_existing_top_up_settlement


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filters = 0

    def filter(self, *_conditions):
        self.filters += 1
        return self

    def first(self):
        return self.result


class FakeDb:
    def __init__(self, result=None):
        self.result = result
        self.queries = 0

    def query(self, _model):
        self.queries += 1
        return FakeQuery(self.result)


def test_existing_settlement_rejects_repeat_payout():
    db = FakeDb(result=SimpleNamespace(status="settled"))
    with pytest.raises(HTTPException) as failure:
        _reject_existing_top_up_settlement(
            db, SimpleNamespace(id=uuid4(), is_top_up=True)
        )
    assert failure.value.status_code == 409
    assert "already settled" in str(failure.value.detail)
    assert db.queries == 1


def test_new_topup_can_continue_to_other_disbursement_guards():
    db = FakeDb()
    _reject_existing_top_up_settlement(
        db, SimpleNamespace(id=uuid4(), is_top_up=True)
    )
    assert db.queries == 1


def test_non_topup_never_queries_settlement_table():
    db = FakeDb(result=object())
    _reject_existing_top_up_settlement(
        db, SimpleNamespace(id=uuid4(), is_top_up=False)
    )
    assert db.queries == 0
