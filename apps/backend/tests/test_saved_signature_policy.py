from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.saved_signature_policy import authorize_saved_signature_use, may_reuse_saved_signature


def valid():
    now = datetime.now(timezone.utc)
    company, borrower = uuid4(), uuid4()
    return dict(
        signature_company_id=company, signature_borrower_id=borrower,
        signature_status="active", signature_opt_in_at=now - timedelta(days=1),
        contract_company_id=company, contract_borrower_id=borrower,
        contract_hash="a" * 64, session_contract_hash="a" * 64,
        session_status="consented", session_expires_at=now + timedelta(minutes=5),
        identity_verified_at=now - timedelta(minutes=1),
        explicit_consent_at=now - timedelta(seconds=30), now=now,
    )


def test_new_contract_requires_own_consent_even_with_saved_signature():
    assert not may_reuse_saved_signature(opted_in=True, specific_contract_approved=False)
    assert not may_reuse_saved_signature(opted_in=False, specific_contract_approved=True)
    assert may_reuse_saved_signature(opted_in=True, specific_contract_approved=True)
    authorize_saved_signature_use(**valid())


@pytest.mark.parametrize("field,value,code", [
    ("signature_status", "revoked", 409),
    ("signature_opt_in_at", None, 409),
    ("contract_hash", "b" * 64, 409),
    ("contract_hash", "invalid", 409),
    ("session_status", "created", 409),
    ("session_status", "completed", 409),
    ("identity_verified_at", None, 409),
    ("explicit_consent_at", None, 409),
])
def test_rejects_invalid_or_unconsented_reuse(field, value, code):
    args = valid()
    args[field] = value
    with pytest.raises(HTTPException) as exc:
        authorize_saved_signature_use(**args)
    assert exc.value.status_code == code


def test_rejects_cross_company_and_borrower():
    for field in ("contract_company_id", "contract_borrower_id"):
        args = valid()
        args[field] = uuid4()
        with pytest.raises(HTTPException) as exc:
            authorize_saved_signature_use(**args)
        assert exc.value.status_code == 403


def test_rejects_expired_and_reordered_consent():
    args = valid()
    args["session_expires_at"] = args["now"]
    with pytest.raises(HTTPException):
        authorize_saved_signature_use(**args)
    args = valid()
    args["identity_verified_at"] = args["explicit_consent_at"] + timedelta(seconds=1)
    with pytest.raises(HTTPException):
        authorize_saved_signature_use(**args)
