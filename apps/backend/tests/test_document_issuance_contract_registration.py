"""Signed contracts cannot be registered from stale staged source bytes."""
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from services.document_issuance_contract_registration import (
    register_signed_contract_locked_issuance,
)
from services.document_issuance_contract_source import StagedSignedContractPdf


PDF = b"%PDF-1.4\ncanonical signed contract\n"


def _fixtures():
    company_id, loan_id, contract_id = uuid4(), uuid4(), uuid4()
    context = SimpleNamespace(company_id=company_id)
    source = SimpleNamespace(
        tenant_id=company_id, loan_id=loan_id, contract_id=contract_id,
        contract_version=4, pdf_bytes=PDF, sha256_hex=sha256(PDF).hexdigest(),
        terms_sha256_hex="a" * 64, file_id=uuid4(),
    )
    staged = SimpleNamespace(
        candidate=SimpleNamespace(tenant_id=company_id),
        source_sha256_hex=source.sha256_hex,
    )
    return Mock(), context, source, StagedSignedContractPdf(source=source, staged=staged)


def _run(db, context, source, staged):
    return register_signed_contract_locked_issuance(
        db=db, context=context, loan_id=source.loan_id,
        contract_id=source.contract_id, contract_version=4,
        prepared=staged, store=Mock(),
        stamp_configuration_version=2, idempotency_key="signed-contract-v4",
    )


def test_final_registration_reloads_contract_and_binds_version_identity():
    db, context, source, staged = _fixtures()
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
        return_value=source,
    ) as load, patch(
        "services.document_issuance_contract_registration.register_locked_staged_document",
        return_value="registered",
    ) as register:
        assert _run(db, context, source, staged) == "registered"
    load.assert_called_once_with(
        db=db, context=context, loan_id=source.loan_id,
        contract_id=source.contract_id, contract_version=4,
    )
    kwargs = register.call_args.kwargs
    assert kwargs["source_pdf"] == PDF
    assert kwargs["source_type"] == "loan_contract"
    assert kwargs["source_id"] == str(source.contract_id)
    assert kwargs["document_type"] == "loan_contract"
    assert kwargs["version"] == 4
    assert kwargs["stamp_configuration_version"] == 2
    assert kwargs["idempotency_key"] == "signed-contract-v4"


@pytest.mark.parametrize("field,value", [
    ("source_sha256_hex", "0" * 64),
    ("candidate_company", uuid4()),
])
def test_stale_pdf_or_wrong_company_rejected_before_registration(field, value):
    db, context, source, staged = _fixtures()
    if field == "candidate_company":
        staged.staged.candidate.tenant_id = value
    else:
        setattr(staged.staged, field, value)
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
        return_value=source,
    ), patch(
        "services.document_issuance_contract_registration.register_locked_staged_document",
    ) as register:
        with pytest.raises(PermissionError, match="changed after locked staging"):
            _run(db, context, source, staged)
    register.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_mutated_signed_contract_identity_rejected():
    db, context, source, staged = _fixtures()
    source.contract_id = uuid4()
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
        return_value=source,
    ), patch(
        "services.document_issuance_contract_registration.register_locked_staged_document",
    ) as register:
        with pytest.raises(PermissionError, match="identity mismatch"):
            register_signed_contract_locked_issuance(
                db=db, context=context, loan_id=source.loan_id,
                contract_id=uuid4(), contract_version=4,
                prepared=staged, store=Mock(),
                stamp_configuration_version=2, idempotency_key="signed-contract-v4",
            )
    register.assert_not_called()


def test_source_validation_failure_does_not_attempt_issuance():
    db, context, source, staged = _fixtures()
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
        side_effect=PermissionError("Contract signature was revoked"),
    ), patch(
        "services.document_issuance_contract_registration.register_locked_staged_document",
    ) as register:
        with pytest.raises(PermissionError, match="revoked"):
            _run(db, context, source, staged)
    register.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("file_id", uuid4()), ("terms_sha256_hex", "b" * 64),
    ("sha256_hex", "0" * 64), ("contract_version", 5),
    ("loan_id", uuid4()),
])
def test_current_contract_change_since_staging_blocks_registration(field, value):
    db, context, source, prepared = _fixtures()
    fresh = SimpleNamespace(**vars(source))
    setattr(fresh, field, value)
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
        return_value=fresh,
    ), patch(
        "services.document_issuance_contract_registration.register_locked_staged_document",
    ) as register:
        with pytest.raises(PermissionError, match="changed since staging|identity mismatch"):
            _run(db, context, source, prepared)
    register.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_swapped_staged_attestation_is_rejected_before_database_lookup():
    db, context, source, prepared = _fixtures()
    other = SimpleNamespace(**vars(source))
    other.contract_version = 99
    swapped = StagedSignedContractPdf(source=other, staged=prepared.staged)
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
    ) as load:
        with pytest.raises(PermissionError, match="identity or version mismatch"):
            _run(db, context, source, swapped)
    load.assert_not_called()


def test_bare_locked_candidate_is_not_a_signed_contract_attestation():
    db, context, source, prepared = _fixtures()
    with patch(
        "services.document_issuance_contract_registration.load_signed_loan_contract_pdf",
    ) as load:
        with pytest.raises(PermissionError, match="attestation required"):
            _run(db, context, source, prepared.staged)
    load.assert_not_called()
