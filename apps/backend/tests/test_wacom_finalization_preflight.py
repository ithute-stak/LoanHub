"""A verified Wacom intent may be considered for review, never auto-signed."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from services.wacom_document_policy import IntentIdentity
from services.wacom_finalization_preflight import finalization_blockers


def fixture():
    company, borrower, contract_id, file_id, operator, pc = (uuid4() for _ in range(6))
    identity = IntentIdentity(company, borrower, contract_id, file_id, operator, pc, "a"*64, "1")
    now = datetime.now(timezone.utc)
    intent = SimpleNamespace(
        company_id=company, borrower_id=borrower, contract_id=contract_id,
        source_file_id=file_id, operator_user_id=operator, workstation_id=pc,
        document_sha256="a"*64, document_version="1",
        binding_sha256=identity.binding_sha256(), status="verified",
        review_by=uuid4(), review_at=now, review_reference="REVIEW-1",
        review_reason="Evidence consent and signer identity checked",
        consent_at=now-timedelta(minutes=2),
        expires_at=now+timedelta(minutes=7),
        consent_reference="CONSENT-1",
        consent_commitment_sha256="b"*64, evidence_file_id=uuid4(),
        evidence_sha256="c"*64,
    )
    contract = SimpleNamespace(id=contract_id, company_id=company, borrower_id=borrower,
                               pdf_file_id=file_id, version=1, borrower_signed_at=None,
                               locked_at=None, status="draft")
    source = SimpleNamespace(id=file_id, company_id=company, checksum_sha256="a"*64,
                             mime_type="application/pdf", is_encrypted=True,
                             is_deleted=False, scan_status="clean")
    evidence = SimpleNamespace(id=intent.evidence_file_id, company_id=company,
                               checksum_sha256="c"*64, linked_entity_type="wacom_client",
                               linked_entity_id=str(borrower),
                               category="wacom_client_capture_verified",
                               is_encrypted=True, is_confidential=True,
                               is_deleted=False, scan_status="clean")
    return intent,contract,source,evidence


def evaluate(items):
    intent,contract,source,evidence=items
    return finalization_blockers(intent=intent,contract=contract,source=source,evidence=evidence)


def test_valid_reviewed_intent_passes_policy_only():
    assert evaluate(fixture()) == []


def test_operator_cannot_review_own_handwriting():
    values=fixture()
    values[0].review_by=values[0].operator_user_id
    assert "capturing_operator_cannot_review" in evaluate(values)


def test_changed_pdf_invalidates_preflight():
    values=fixture()
    values[2].checksum_sha256="d"*64
    assert "source_pdf_unavailable_or_changed" in evaluate(values)


def test_changed_contract_version_invalidates_preflight():
    values=fixture()
    values[1].version=2
    assert "contract_version_or_status_changed" in evaluate(values)


def test_reviewed_evidence_required():
    values=fixture()
    values[3].category="wacom_client_signature_pending"
    assert "reviewed_evidence_unavailable_or_changed" in evaluate(values)


def test_document_binding_must_be_intact():
    values=fixture()
    values[0].binding_sha256="e"*64
    assert "document_binding_invalid" in evaluate(values)


def test_consent_must_precede_review_and_expiry():
    values=fixture()
    values[0].consent_at=values[0].review_at+timedelta(seconds=5)
    assert "review_precedes_consent" in evaluate(values)
    values[0].expires_at=values[0].review_at-timedelta(minutes=5)
    assert "consent_outside_prepared_window" in evaluate(values)


def test_signed_contract_cannot_pass():
    values=fixture()
    values[1].borrower_signed_at=datetime.now(timezone.utc)
    assert "contract_version_or_status_changed" in evaluate(values)
