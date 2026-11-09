"""Final Wacom commit-policy tests; none perform a real signing transaction."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from services import wacom_execution_commit_policy as policy


def example():
    now = datetime.now(timezone.utc)
    company, contract, intent_id, packet_id, authorization_id = [uuid4() for _ in range(5)]
    operator, approver = uuid4(), uuid4()
    pdf = b"%PDF-SYNTHETIC-RENDERED-CANDIDATE"
    digest = sha256(pdf).hexdigest()
    field = "f" * 64
    intent = R(id=intent_id, company_id=company, contract_id=contract,
               source_file_id=uuid4(), document_sha256="a"*64,
               evidence_sha256="b"*64, binding_sha256="c"*64)
    approval = R()
    packet = R(id=packet_id, packet_file_id=uuid4())
    authorization = R(
        id=authorization_id, status="approved", consumed_at=None,
        authorized_at=now-timedelta(seconds=20),
        field_binding_sha256=field,
    )
    receipt = R(
        company_id=company, contract_id=contract, intent_id=intent_id,
        authorization_id=authorization_id, packet_id=packet_id,
        status="reserved", executed_file_id=None, executed_pdf_sha256=digest,
        executed_at=None,
        reserved_by=operator, reserved_at=now-timedelta(seconds=10),
        document_sha256=intent.document_sha256,
        evidence_sha256=intent.evidence_sha256,
        binding_sha256=intent.binding_sha256,
        field_binding_sha256=field,
    )
    file = R(
        company_id=company, id=uuid4(), is_deleted=False,
        is_encrypted=True, is_confidential=True, scan_status="clean",
        mime_type="application/pdf", category="wacom_execution_candidate",
        checksum_sha256=digest,
    )
    receipt.executed_file_id = file.id
    return dict(
        intent=intent, approval=approval, packet=packet,
        execution_authorization=authorization, receipt=receipt,
        contract=R(), source=R(), evidence=R(),
        candidate_file=file, executing_user_id=operator,
        source_pdf=b"%PDF-original", handwriting_png=b"handwriting",
        candidate_pdf=pdf, candidate_sha256=digest, now=now,
    )


@pytest.fixture(autouse=True)
def mock_upstream_validators(monkeypatch):
    # Upstream is tested in dedicated tests; isolate this commit gate.
    monkeypatch.setattr(policy, "reserve_execution_blockers", lambda **kwargs: [])
    monkeypatch.setattr(policy, "stored_field_matches", lambda **kwargs: True)


def blockers(values):
    return policy.execution_commit_blockers(**values)


def test_commit_gate_accepts_consistent_synthetic_candidate():
    assert blockers(example()) == []


@pytest.mark.parametrize("record,field,value,denial", [
    ("receipt", "status", "executed", "execution_receipt_not_bound_to_candidate"),
    ("receipt", "executed_at", datetime.now(timezone.utc), "execution_receipt_not_bound_to_candidate"),
    ("receipt", "authorization_id", uuid4(), "execution_receipt_scope_mismatch"),
    ("receipt", "field_binding_sha256", "0"*64, "execution_receipt_field_changed"),
    ("receipt", "document_sha256", "0"*64, "execution_receipt_hashes_changed"),
    ("receipt", "reserved_by", uuid4(), "execution_reservation_owner_changed"),
    ("candidate_file", "company_id", uuid4(), "candidate_storage_not_verified"),
    ("candidate_file", "is_encrypted", False, "candidate_storage_not_verified"),
    ("candidate_file", "scan_status", "pending", "candidate_storage_not_verified"),
    ("candidate_file", "category", "general", "candidate_storage_not_verified"),
    ("candidate_file", "checksum_sha256", "0"*64, "candidate_storage_not_verified"),
    ("execution_authorization", "consumed_at", datetime.now(timezone.utc), "execution_authorization_already_consumed"),
    ("execution_authorization", "authorized_at", None, "execution_authorizer_missing_timestamp"),
])
def test_denies_mutated_receipt_or_storage(record, field, value, denial):
    data = example()
    setattr(data[record], field, value)
    assert denial in blockers(data)


def test_denies_candidate_byte_tampering():
    data = example()
    data["candidate_pdf"] += b"changed"
    assert "rendered_candidate_hash_mismatch" in blockers(data)


def test_denies_original_file_overwrite():
    data = example()
    data["candidate_file"].id = data["intent"].source_file_id
    assert "candidate_overwrites_original" in blockers(data)


def test_denies_overwriting_evidence_packet():
    data = example()
    data["candidate_file"].id = data["packet"].packet_file_id
    assert "candidate_overwrites_original" in blockers(data)


def test_denies_changed_signature_field(monkeypatch):
    monkeypatch.setattr(policy, "stored_field_matches", lambda **kwargs: False)
    assert "approved_field_changed" in blockers(example())


def test_upstream_gate_denials_propagate(monkeypatch):
    monkeypatch.setattr(policy, "reserve_execution_blockers", lambda **kwargs: ["intent_expired"])
    assert "intent_expired" in blockers(example())


def test_requires_complete_context():
    data = example()
    data["receipt"] = None
    assert blockers(data) == ["missing_commit_context"]


def test_no_implicit_signing_or_storage_in_policy():
    import inspect
    code = inspect.getsource(policy)
    for forbidden in ("db.commit(", "store_bytes(", "borrower_signed_at =", "contract.status ="):
        assert forbidden not in code
