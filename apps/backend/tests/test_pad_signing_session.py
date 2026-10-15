from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException

from services.pad_signing_session import PadSessionState, advance_session, new_session

COMPANY = UUID("11111111-1111-1111-1111-111111111111")
CONTRACT = UUID("22222222-2222-2222-2222-222222222222")
OPERATOR = UUID("33333333-3333-3333-3333-333333333333")
HASH = "a" * 64
NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def session():
    return new_session(company_id=COMPANY, contract_id=CONTRACT, contract_hash=HASH,
                       operator_id=OPERATOR, now=NOW)


def advance(row, action, **kwargs):
    data = dict(company_id=COMPANY, contract_id=CONTRACT, contract_hash=HASH,
                operator_id=OPERATOR, now=NOW + timedelta(seconds=1))
    data.update(kwargs)
    return advance_session(row, action=action, **data)


def test_requires_verified_consent_before_capture():
    row = session()
    with pytest.raises(HTTPException):
        advance(row, "capture", evidence_sha256="b" * 64)
    with pytest.raises(HTTPException):
        advance(row, "consent", explicit_consent=True)
    consented = advance(row, "consent", identity_verified=True, explicit_consent=True)
    assert consented.state == PadSessionState.CONSENTED
    captured = advance(consented, "capture", evidence_sha256="b" * 64)
    assert captured.state == PadSessionState.CAPTURED
    assert captured.evidence_sha256 == "b" * 64
    with pytest.raises(HTTPException):
        advance(captured, "complete")


@pytest.mark.parametrize("field,value", [
    ("company_id", UUID("99999999-1111-1111-1111-111111111111")),
    ("contract_id", UUID("99999999-2222-2222-2222-222222222222")),
    ("operator_id", UUID("99999999-3333-3333-3333-333333333333")),
    ("contract_hash", "c" * 64),
])
def test_cross_context_session_use_rejected(field, value):
    with pytest.raises(HTTPException) as exc:
        advance(session(), "cancel", **{field: value})
    assert exc.value.status_code == 403


def test_expiry_blocks_capture_and_is_terminal():
    row = advance(session(), "consent", identity_verified=True, explicit_consent=True)
    expired = advance(row, "capture", now=NOW + timedelta(minutes=11),
                      evidence_sha256="b" * 64)
    assert expired.state == PadSessionState.EXPIRED
    with pytest.raises(HTTPException):
        advance(expired, "cancel")


def test_cancelled_cannot_be_reused():
    cancelled = advance(session(), "cancel")
    with pytest.raises(HTTPException):
        advance(cancelled, "consent", identity_verified=True, explicit_consent=True)
