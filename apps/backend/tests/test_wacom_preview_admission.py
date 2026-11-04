from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from services.wacom_preview_admission import authorize_wacom_preview_admission


NOW = datetime(2026, 11, 4, 10, tzinfo=timezone.utc)
COMPANY, OPERATOR, CONTRACT, SESSION = (uuid4() for _ in range(4))
HASH = "a" * 64


def active():
    return SimpleNamespace(
        id=SESSION, company_id=COMPANY, operator_user_id=OPERATOR,
        contract_id=CONTRACT, contract_hash=HASH,
        status="created", evidence_sha256=None,
        expires_at=NOW + timedelta(minutes=5),
    )


def admit(row, **overrides):
    args = dict(
        session=row, authenticated_company_id=COMPANY,
        authenticated_operator_id=OPERATOR, current_contract_id=CONTRACT,
        current_contract_hash=HASH, expected_session_id=SESSION, now=NOW,
    )
    args.update(overrides)
    return authorize_wacom_preview_admission(**args)


def test_valid_created_session_only_allows_temporary_preview():
    assert admit(active()) is None
    row = active()
    row.status = "consented"
    assert admit(row) is None


@pytest.mark.parametrize("field,wrong", [
    ("authenticated_company_id", uuid4()),
    ("authenticated_operator_id", uuid4()),
    ("current_contract_id", uuid4()),
    ("expected_session_id", uuid4()),
    ("current_contract_hash", "b" * 64),
])
def test_cross_context_rejected(field, wrong):
    with pytest.raises(HTTPException):
        admit(active(), **{field: wrong})


@pytest.mark.parametrize("status", [
    "cancelled", "expired", "completed", "captured", None, "unknown",
])
def test_closed_or_unknown_status_rejected(status):
    row = active()
    row.status = status
    with pytest.raises(HTTPException):
        admit(row)


def test_expired_missing_or_mutated_session_rejected():
    row = active()
    row.expires_at = NOW
    with pytest.raises(HTTPException):
        admit(row)
    row = active()
    row.contract_hash = "b" * 64
    with pytest.raises(HTTPException):
        admit(row)
    row = active()
    row.evidence_sha256 = "c" * 64
    with pytest.raises(HTTPException):
        admit(row)
    with pytest.raises(HTTPException):
        admit(None)


def test_rejects_untrusted_time_and_missing_hash():
    with pytest.raises(HTTPException):
        admit(active(), now=datetime(2026, 11, 4, 10))
    with pytest.raises(HTTPException):
        admit(active(), current_contract_hash="invalid")
    row = active()
    row.expires_at = datetime(2026, 11, 4, 10)
    with pytest.raises(HTTPException):
        admit(row)
