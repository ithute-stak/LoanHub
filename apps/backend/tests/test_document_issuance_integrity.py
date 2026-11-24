from uuid import uuid4

from services.document_issuance_integrity import (
    IssuanceFingerprint, new_public_document_id, pdf_fingerprint,
    verify_exact_document,
)


def test_exact_pdf_bytes_only_and_revocation_state():
    tenant = uuid4()
    identifier = new_public_document_id()
    pdf = b"%PDF-1.4\noriginal\n"
    record = IssuanceFingerprint(tenant, identifier, pdf_fingerprint(pdf), "issued")
    assert verify_exact_document(
        pdf=pdf, record=record, expected_tenant_id=tenant,
        requested_public_id=identifier,
    ) == "verified"
    assert verify_exact_document(
        pdf=pdf + b"tamper", record=record, expected_tenant_id=tenant,
        requested_public_id=identifier,
    ) == "altered"
    assert verify_exact_document(
        pdf=pdf, record=record, expected_tenant_id=uuid4(),
        requested_public_id=identifier,
    ) == "not_found"
    assert verify_exact_document(
        pdf=pdf, record=record, expected_tenant_id=tenant,
        requested_public_id="copied-but-incorrect",
    ) == "not_found"
    assert verify_exact_document(
        pdf=pdf, record=IssuanceFingerprint(tenant, identifier, record.sha256_hex, "revoked"),
        expected_tenant_id=tenant, requested_public_id=identifier,
    ) == "revoked"
    assert verify_exact_document(
        pdf=pdf, record=IssuanceFingerprint(tenant, identifier, record.sha256_hex, "superseded"),
        expected_tenant_id=tenant, requested_public_id=identifier,
    ) == "superseded"


def test_public_ids_are_random_and_nonempty():
    assert new_public_document_id() != new_public_document_id()
    assert len(new_public_document_id()) >= 24
