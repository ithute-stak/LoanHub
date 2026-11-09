"""Borrower-account consent must never be supplied by an employee."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4
import inspect

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from services.wacom_borrower_affirmation_policy import (
    borrower_affirmation_blockers, affirmation_digest,
)
from routers import wacom_borrower_affirmations as routes


def records():
    now = datetime.now(timezone.utc)
    company, borrower_id, user_id, intent_id, auth_id, receipt_id, file_id = [uuid4() for _ in range(7)]
    pdf = b"%PDF-1.4\nBorrower exact document\n%%EOF"
    digest = sha256(pdf).hexdigest()
    field = "f"*64
    borrower = R(id=borrower_id, user_id=user_id)
    challenge = R(
        id=uuid4(), borrower_id=borrower_id, company_id=company,
        contract_id=uuid4(), intent_id=intent_id,
        authorization_id=auth_id, receipt_id=receipt_id,
        candidate_sha256=digest, field_binding_sha256=field,
        requested_at=now-timedelta(seconds=40), expires_at=now+timedelta(seconds=30),
        status="pending", verified_at=None, consumed_at=None,
        workstation_proof_at=now-timedelta(seconds=20),
        workstation_proof_by=uuid4(), workstation_proof_sha256="a"*64,
        borrower_affirmed_at=None, borrower_affirmed_user_id=None,
        borrower_affirmation_sha256=None,
    )
    authorization = R(
        id=auth_id, company_id=company,
        status="approved", consumed_at=None, field_binding_sha256=field,
    )
    receipt = R(
        id=receipt_id, company_id=company, contract_id=challenge.contract_id,
        intent_id=intent_id, authorization_id=auth_id,
        executed_file_id=file_id, executed_pdf_sha256=digest,
        status="reserved", executed_at=None,
    )
    file = R(
        id=file_id, company_id=company, checksum_sha256=digest,
        is_deleted=False, is_encrypted=True, is_confidential=True,
        scan_status="clean", category="wacom_execution_candidate",
        mime_type="application/pdf", size_bytes=len(pdf),
    )
    return dict(
        challenge=challenge, borrower=borrower, authorization=authorization,
        receipt=receipt, candidate_file=file, user_id=user_id,
        candidate_pdf=pdf, displayed_candidate_sha256=digest,
        displayed_field_sha256=field, now=now,
    )


def reasons(**kwargs):
    return borrower_affirmation_blockers(**kwargs)


def test_valid_synthetic_borrower_affirmation_not_contract_execution():
    data = records()
    assert reasons(**data) == []
    assert data["challenge"].status == "pending"


@pytest.mark.parametrize("group,attribute,value,reason", [
    ("borrower", "user_id", uuid4(), "authenticated_borrower_mismatch"),
    ("challenge", "borrower_id", uuid4(), "authenticated_borrower_mismatch"),
    ("challenge", "company_id", uuid4(), "borrower_affirmation_company_mismatch"),
    ("challenge", "status", "verified", "borrower_affirmation_challenge_unavailable"),
    ("challenge", "borrower_affirmed_at", datetime.now(timezone.utc), "borrower_affirmation_challenge_unavailable"),
    ("challenge", "workstation_proof_at", None, "workstation_key_proof_missing"),
    ("authorization", "status", "consumed", "borrower_affirmation_challenge_unavailable"),
    ("receipt", "executed_pdf_sha256", "0"*64, "borrower_affirmation_document_mismatch"),
    ("candidate_file", "is_encrypted", False, "borrower_affirmation_candidate_invalid"),
    ("candidate_file", "is_deleted", True, "borrower_affirmation_candidate_invalid"),
])
def test_reject_invalid_affirmation(group, attribute, value, reason):
    data = records()
    setattr(data[group], attribute, value)
    assert reason in reasons(**data)


def test_wrong_document_hash_rejected():
    data = records()
    data["displayed_candidate_sha256"] = "a"*64
    assert "borrower_affirmation_document_mismatch" in reasons(**data)


def test_modified_pdf_bytes_rejected():
    data = records()
    data["candidate_pdf"] += b"tampered"
    assert "borrower_affirmation_candidate_invalid" in reasons(**data)


def test_expired_approval_rejected():
    data = records()
    data["challenge"].expires_at = data["now"]-timedelta(seconds=1)
    assert "borrower_affirmation_challenge_unavailable" in reasons(**data)


def test_commitment_changes_with_borrower_identity():
    data = records()
    kwargs = dict(
        challenge_id=data["challenge"].id, candidate_sha256=data["displayed_candidate_sha256"],
        field_sha256=data["displayed_field_sha256"], now=data["now"],
    )
    a = affirmation_digest(user_id=data["user_id"], **kwargs)
    b = affirmation_digest(user_id=uuid4(), **kwargs)
    assert len(a) == 64 and a != b


def test_unsigned_request_cannot_simulate_yes():
    with pytest.raises(ValidationError):
        routes.AffirmCandidate(
            affirmative_choice=False,
            displayed_candidate_sha256="a"*64,
            displayed_field_sha256="b"*64,
        )


def test_route_requires_borrower_account():
    from database.models.enums import UserRole
    with pytest.raises(HTTPException) as exc:
        routes._borrower(None, R(role=UserRole.COMPANY_ADMIN, id=uuid4()))
    assert exc.value.status_code == 403


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(routes.FLAG, raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def test_no_contract_execution_in_routes():
    source = inspect.getsource(routes)
    assert "contract.borrower_signed_at =" not in source
    assert "authorization.consumed_at =" not in source
    assert "contract.status =" not in source
    assert "physical_pen_verified" in source


def test_preview_requires_authenticated_borrower_and_valid_file_bytes():
    source = inspect.getsource(routes.review_candidate_pdf)
    assert "_borrower(db, ctx.user)" in source
    assert "_verified_bytes(candidate)" in source
    assert "borrower_affirmation_blockers(" in source
    assert 'Cache-Control": "no-store, private"' in source
