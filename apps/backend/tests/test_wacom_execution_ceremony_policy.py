"""Independent Wacom signing ceremony cannot reuse archived consent or approvals."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from services.wacom_execution_ceremony_policy import execution_ceremony_blockers


def fixtures():
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    company, borrower, contract_id, intent_id, authorization_id, file_id = [uuid4() for _ in range(6)]
    people = [uuid4() for _ in range(7)]
    candidate = b"%PDF-1.4\nsynthetic finalized candidate\n%%EOF"
    digest = sha256(candidate).hexdigest()
    field = "a" * 64
    intent = R(
        id=intent_id, company_id=company, contract_id=contract_id,
        borrower_id=borrower, workstation_id=uuid4(),
        source_file_id=uuid4(), document_version="1",
        document_sha256="b"*64, evidence_sha256="c"*64,
        binding_sha256="d"*64, operator_user_id=people[0], review_by=people[1],
    )
    auth = R(
        id=authorization_id, company_id=company, intent_id=intent_id,
        contract_id=contract_id, status="approved", consumed_at=None,
        field_binding_sha256=field, requested_by=people[2],
        authorized_by=people[3],
    )
    receipt = R(
        id=uuid4(), company_id=company, contract_id=contract_id,
        intent_id=intent_id, authorization_id=authorization_id,
        executed_file_id=file_id, executed_pdf_sha256=digest,
        field_binding_sha256=field,
        document_sha256="b"*64, evidence_sha256="c"*64, binding_sha256="d"*64,
        status="reserved", executed_at=None, reserved_by=people[4],
    )
    contract = R(
        id=contract_id, company_id=company, borrower_id=borrower,
        version=1, status="draft", borrower_signed_at=None,
        locked_at=None, pdf_file_id=intent.source_file_id,
    )
    file = R(
        id=file_id, company_id=company, category="wacom_execution_candidate",
        mime_type="application/pdf", is_encrypted=True, is_confidential=True,
        is_deleted=False, scan_status="clean", checksum_sha256=digest,
    )
    consent = R(
        company_id=company, borrower_id=borrower, contract_id=contract_id,
        candidate_sha256=digest, field_binding_sha256=field,
        affirmative_choice=True, consent_reference="fresh-consent",
        affirmed_at=now-timedelta(seconds=30),
    )
    proof = R(
        company_id=company, workstation_id=intent.workstation_id,
        borrower_id=borrower, contract_id=contract_id,
        candidate_sha256=digest, signature_verified=True,
        hardware_evidence_reference="physical-stu540-check",
        verified_at=now-timedelta(seconds=20),
    )
    legal = R(
        company_id=company, status="approved",
        candidate_sha256=digest, legal_basis_reference="reviewed-test-basis",
        reviewer_user_id=people[5], released_at=now-timedelta(seconds=10),
    )
    return dict(
        intent=intent, authorization=auth, receipt=receipt,
        contract=contract, candidate_file=file,
        fresh_consent=consent, device_proof=proof, legal_release=legal,
        executor_id=people[6], candidate_pdf=candidate, now=now,
    )


def deny(values):
    return execution_ceremony_blockers(**values)


def test_complete_synthetic_readiness_context_not_an_execution():
    values = fixtures()
    assert deny(values) == []
    assert values["contract"].borrower_signed_at is None


@pytest.mark.parametrize("section,attribute,value,expected", [
    ("fresh_consent", "affirmative_choice", False, "fresh_borrower_affirmation_missing"),
    ("fresh_consent", "candidate_sha256", "0"*64, "fresh_borrower_affirmation_missing"),
    ("fresh_consent", "consent_reference", None, "fresh_borrower_affirmation_missing"),
    ("fresh_consent", "borrower_id", uuid4(), "fresh_borrower_affirmation_missing"),
    ("device_proof", "signature_verified", False, "fresh_physical_device_proof_missing"),
    ("device_proof", "workstation_id", uuid4(), "fresh_physical_device_proof_missing"),
    ("device_proof", "hardware_evidence_reference", None, "fresh_physical_device_proof_missing"),
    ("legal_release", "status", "pending", "independent_legal_release_missing"),
    ("legal_release", "candidate_sha256", "0"*64, "independent_legal_release_missing"),
    ("legal_release", "legal_basis_reference", None, "independent_legal_release_missing"),
    ("authorization", "consumed_at", datetime(2026,11,9,tzinfo=timezone.utc), "execution_already_closed"),
    ("receipt", "status", "executed", "execution_already_closed"),
    ("contract", "status", "signed", "contract_changed_or_already_executed"),
    ("contract", "pdf_file_id", uuid4(), "contract_changed_or_already_executed"),
    ("candidate_file", "is_encrypted", False, "execution_candidate_not_verified"),
    ("candidate_file", "checksum_sha256", "0"*64, "execution_candidate_not_verified"),
    ("receipt", "field_binding_sha256", "0"*64, "execution_binding_mismatch"),
])
def test_fail_closed_if_context_is_changed(section, attribute, value, expected):
    values = fixtures()
    setattr(values[section], attribute, value)
    assert expected in deny(values)


def test_old_consent_cannot_substitute_for_fresh_execution_affirmation():
    values = fixtures()
    values["fresh_consent"].affirmed_at -= timedelta(hours=1)
    assert "fresh_borrower_affirmation_missing" in deny(values)


def test_device_proof_must_follow_borrower_affirmation():
    values = fixtures()
    values["device_proof"].verified_at = values["fresh_consent"].affirmed_at-timedelta(seconds=1)
    assert "fresh_physical_device_proof_missing" in deny(values)


def test_no_future_dated_affirmation():
    values = fixtures()
    values["fresh_consent"].affirmed_at = values["now"]+timedelta(seconds=1)
    assert "fresh_borrower_affirmation_missing" in deny(values)


def test_changed_candidate_bytes_rejected():
    values = fixtures()
    values["candidate_pdf"] += b"tampered"
    assert "execution_candidate_not_verified" in deny(values)


def test_independent_executor_and_legal_review_required():
    values = fixtures()
    values["executor_id"] = values["authorization"].authorized_by
    assert "execution_operator_not_independent" in deny(values)
    values = fixtures()
    values["legal_release"].reviewer_user_id = values["authorization"].requested_by
    assert "legal_reviewer_not_independent" in deny(values)


def test_missing_physical_proof_never_succeeds():
    values = fixtures()
    values["device_proof"] = None
    assert deny(values) == ["execution_ceremony_context_missing"]


def test_no_persistence_or_implicit_signature():
    import inspect
    from services import wacom_execution_ceremony_policy as policy
    source = inspect.getsource(policy)
    for forbidden in ("db.commit(", "contract.status =", "borrower_signed_at =", "store_bytes("):
        assert forbidden not in source
