"""Phase 21 execution preflight: synthetic evidence, no live signing."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as Record
from uuid import uuid4

import pytest
from services.wacom_execution_preflight import execution_preflight_blockers


def fixture():
    now = datetime(2026, 11, 9, 5, tzinfo=timezone.utc)
    people = [uuid4() for _ in range(7)]
    company, intent_id, contract_id, approval_id = [uuid4() for _ in range(4)]
    source, ink = b"%PDF-synthetic-source", b"\x89PNG\r\n\x1a\nsynthetic"
    document_hash, ink_hash = sha256(source).hexdigest(), sha256(ink).hexdigest()
    binding_hash = "a" * 64
    intent = Record(
        id=intent_id, company_id=company, contract_id=contract_id,
        status="verified", review_by=people[1], review_at=now-timedelta(minutes=3),
        operator_user_id=people[0], consent_at=now-timedelta(minutes=4),
        consent_reference="consent-ref", consent_commitment_sha256="b"*64,
        expires_at=now+timedelta(minutes=10),
        document_sha256=document_hash, evidence_sha256=ink_hash,
        binding_sha256=binding_hash,
    )
    approval = Record(
        id=approval_id, intent_id=intent_id, contract_id=contract_id,
        company_id=company, status="consumed", consumed_at=now-timedelta(minutes=1),
        decided_by=people[3], requested_by=people[2], decision_reference="approved",
        decided_at=now-timedelta(minutes=2), expires_at=now+timedelta(minutes=2),
        document_sha256=document_hash, evidence_sha256=ink_hash,
        binding_sha256=binding_hash,
    )
    packet = Record(
        approval_id=approval_id, intent_id=intent_id, contract_id=contract_id,
        company_id=company, source_sha256=document_hash,
        handwriting_sha256=ink_hash, created_by_user_id=people[4],
        archived_at=now-timedelta(minutes=1), packet_file_id=uuid4(),
    )
    permit = Record(
        intent_id=intent_id, contract_id=contract_id, company_id=company,
        status="approved", consumed_at=None, authorized_by=people[5],
        expires_at=now+timedelta(minutes=1),
        document_sha256=document_hash, evidence_sha256=ink_hash,
        binding_sha256=binding_hash,
    )
    return dict(intent=intent, approval=approval, packet=packet,
                execution_authorization=permit, executing_user_id=people[6],
                source_pdf=source, handwriting_png=ink, now=now)


def blockers(values):
    return execution_preflight_blockers(**values)


def test_valid_synthetic_preflight_not_executed():
    assert blockers(fixture()) == []


@pytest.mark.parametrize("record,attribute,value,expected", [
    ("intent", "status", "cancelled", "review_not_verified"),
    ("intent", "consent_reference", None, "consent_missing"),
    ("approval", "status", "approved", "archival_approval_not_consumed"),
    ("packet", "packet_file_id", None, "packet_not_archived"),
    ("execution_authorization", "status", "consumed", "execution_permit_unavailable"),
    ("execution_authorization", "document_sha256", "c"*64, "document_sha256_execution_mismatch"),
    ("packet", "source_sha256", "c"*64, "archived_source_mismatch"),
    ("intent", "company_id", uuid4(), "company_mismatch"),
    ("approval", "contract_id", uuid4(), "contract_mismatch"),
    ("packet", "approval_id", uuid4(), "archived_approval_mismatch"),
])
def test_denies_mutated_state(record, attribute, value, expected):
    values = fixture()
    setattr(values[record], attribute, value)
    assert expected in blockers(values)


def test_denies_expired_permit():
    values = fixture()
    values["execution_authorization"].expires_at = values["now"]
    assert "execution_permit_expired" in blockers(values)


def test_denies_expired_intent():
    values = fixture()
    values["intent"].expires_at = values["now"]
    assert "intent_expired" in blockers(values)


def test_denies_tampered_bytes():
    values = fixture()
    values["source_pdf"] += b"changed"
    values["handwriting_png"] += b"changed"
    reasons = blockers(values)
    assert "source_bytes_mismatch" in reasons
    assert "handwriting_bytes_mismatch" in reasons


def test_denies_same_person_approval_execution():
    values = fixture()
    values["executing_user_id"] = values["execution_authorization"].authorized_by
    assert "separation_of_duties_violation" in blockers(values)


def test_denies_capture_operator_authorization():
    values = fixture()
    values["execution_authorization"].authorized_by = values["intent"].operator_user_id
    assert "separation_of_duties_violation" in blockers(values)


def test_denies_missing_records():
    values = fixture()
    values["packet"] = None
    assert blockers(values) == ["missing_execution_records"]


def test_denies_naive_expiry():
    values = fixture()
    values["execution_authorization"].expires_at = datetime(2026, 11, 9, 6)
    assert "execution_permit_expired" in blockers(values)


def test_policy_does_not_mutate_or_sign():
    import inspect
    source = inspect.getsource(execution_preflight_blockers)
    for forbidden in ("db.commit(", "PdfWriter(", "store_bytes(", "signed_at ="):
        assert forbidden not in source
