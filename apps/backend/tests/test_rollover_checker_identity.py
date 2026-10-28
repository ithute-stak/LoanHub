"""Unit tests for rollover checker identity eligibility (not approval)."""
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from services.rollover_checker_identity import verify_rollover_checker_identity


class Query:
    def __init__(self, result):
        self.result = result
    def filter(self, *args):
        return self
    def one_or_none(self):
        return self.result
    def first(self):
        return self.result


class DB:
    def __init__(self, account, membership):
        self.results = [account, membership]
    def query(self, *args):
        return Query(self.results.pop(0))


def test_distinct_active_verified_tenant_checker():
    maker, checker, company = uuid4(), uuid4(), uuid4()
    result = verify_rollover_checker_identity(
        DB(SimpleNamespace(id=checker), (uuid4(),)),
        company_id=company, maker_user_id=maker, checker_user_id=checker,
    )
    assert result == checker


def test_same_maker_checker_fails_closed():
    person = uuid4()
    with pytest.raises(HTTPException) as exc:
        verify_rollover_checker_identity(
            DB(None, None), company_id=uuid4(), maker_user_id=person,
            checker_user_id=person,
        )
    assert exc.value.status_code == 409


@pytest.mark.parametrize("account,membership", [
    (None, None),
    (SimpleNamespace(id=uuid4()), None),
])
def test_absent_checker_or_tenant_authorization_fails_closed(account, membership):
    with pytest.raises(HTTPException) as exc:
        verify_rollover_checker_identity(
            DB(account, membership), company_id=uuid4(),
            maker_user_id=uuid4(), checker_user_id=uuid4(),
        )
    assert exc.value.status_code == 409
