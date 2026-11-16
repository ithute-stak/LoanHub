from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as R
from uuid import uuid4
import pytest

from services.wacom_execution_challenge_gate import challenge_execution_blockers


def context():
    now = datetime(2026, 11, 16, 15, tzinfo=timezone.utc)
    company, borrower, contract, intent_id, auth_id, receipt_id, workstation = [uuid4() for _ in range(7)]
    intent = R(id=intent_id, company_id=company, borrower_id=borrower,
               contract_id=contract, workstation_id=workstation)
    auth = R(id=auth_id, field_binding_sha256="a"*64)
    receipt = R(id=receipt_id, contract_id=contract, authorization_id=auth_id,
                executed_pdf_sha256="b"*64)
    challenge = R(company_id=company, borrower_id=borrower, contract_id=contract,
                  intent_id=intent_id, authorization_id=auth_id, receipt_id=receipt_id,
                  workstation_id=workstation, candidate_sha256="b"*64,
                  field_binding_sha256="a"*64, challenge_sha256="c"*64,
                  status="verified", requested_at=now-timedelta(seconds=60),
                  expires_at=now+timedelta(seconds=60),
                  verified_at=now-timedelta(seconds=5), consumed_at=None,
                  workstation_proof_at=now-timedelta(seconds=30),
                  borrower_affirmed_at=now-timedelta(seconds=20),
                  workstation_proof_by=uuid4(), borrower_affirmed_user_id=borrower,
                  workstation_proof_sha256="d"*64,
                  borrower_affirmation_sha256="e"*64)
    return dict(challenge=challenge, intent=intent, authorization=auth,
                receipt=receipt, candidate_sha256="b"*64, now=now)


def test_synthetic_ready_challenge_is_not_execution():
    ctx = context()
    assert challenge_execution_blockers(**ctx) == []
    assert ctx["challenge"].consumed_at is None


@pytest.mark.parametrize("field,value,reason", [
    ("status", "consumed", "challenge_not_single_use_ready"),
    ("consumed_at", datetime(2026, 11, 16, 15, tzinfo=timezone.utc), "challenge_not_single_use_ready"),
    ("receipt_id", uuid4(), "challenge_reference_mismatch"),
    ("workstation_id", uuid4(), "challenge_reference_mismatch"),
    ("candidate_sha256", "f"*64, "challenge_document_binding_mismatch"),
    ("field_binding_sha256", "f"*64, "challenge_document_binding_mismatch"),
    ("workstation_proof_sha256", None, "challenge_evidence_incomplete"),
    ("borrower_affirmed_at", None, "challenge_evidence_incomplete"),
])
def test_reject_invalid_challenge(field, value, reason):
    ctx = context()
    setattr(ctx["challenge"], field, value)
    assert reason in challenge_execution_blockers(**ctx)


def test_expired_challenge_cannot_be_replayed():
    ctx = context()
    ctx["challenge"].expires_at = ctx["now"]
    assert "challenge_expired_or_invalid" in challenge_execution_blockers(**ctx)


def test_overlong_challenge_lifetime_rejected():
    ctx = context()
    ctx["challenge"].expires_at += timedelta(hours=1)
    assert "challenge_expired_or_invalid" in challenge_execution_blockers(**ctx)


def test_missing_challenge_denied():
    ctx = context()
    ctx["challenge"] = None
    assert challenge_execution_blockers(**ctx) == ["missing_execution_challenge"]
