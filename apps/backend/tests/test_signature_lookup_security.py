"""Staging National ID privacy budget tests without a live PostgreSQL server."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services import signature_lookup_security as security


def test_audits_lookup_attempt_without_personal_values():
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 2
    company, user = uuid4(), uuid4()
    security.reserve_lookup_attempt(db, company_id=company, operator_id=user)
    db.execute.assert_called_once()
    sql, params = db.execute.call_args.args
    assert "pg_advisory_xact_lock" in str(sql)
    assert isinstance(params["key"], int)
    event = db.add.call_args.args[0]
    assert event.company_id == company
    assert event.user_id == user
    assert event.action == security.ACTION
    assert event.event_data["contains_personal_data"] is False
    assert "national_id" not in event.event_data
    db.commit.assert_called_once()


def test_budget_exhaustion_returns_429_and_no_lookup_event():
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = security.MAX_ATTEMPTS
    with pytest.raises(HTTPException) as raised:
        security.reserve_lookup_attempt(db, company_id=uuid4(), operator_id=uuid4())
    assert raised.value.status_code == 429
    db.rollback.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_audit_database_error_fails_closed():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(HTTPException) as raised:
        security.reserve_lookup_attempt(db, company_id=uuid4(), operator_id=uuid4())
    assert raised.value.status_code == 503
    db.rollback.assert_called_once()
    db.add.assert_not_called()


def test_invalid_audit_count_fails_closed():
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = None
    with pytest.raises(HTTPException) as raised:
        security.reserve_lookup_attempt(db, company_id=uuid4(), operator_id=uuid4())
    assert raised.value.status_code == 503
    db.commit.assert_not_called()


def test_lock_key_stable_for_same_operator_and_company():
    company, user = uuid4(), uuid4()
    keys = []
    for _ in range(2):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        security.reserve_lookup_attempt(db, company_id=company, operator_id=user)
        keys.append(db.execute.call_args.args[1]["key"])
    assert keys[0] == keys[1]
