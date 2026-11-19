"""Signed LoanContract source must match its frozen terms and current PDF."""
import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from services.document_issuance_contract_source import (
    load_signed_loan_contract_pdf, stage_signed_loan_contract_pdf,
)

PDF = b"%PDF-1.4\nSigned company agreement\n"


def _case():
    tenant, issuer, loan_id, borrower_id, contract_id, file_id = [uuid4() for _ in range(6)]
    context = SimpleNamespace(
        company_id=tenant, company=SimpleNamespace(id=tenant),
        user=SimpleNamespace(id=issuer), staff=SimpleNamespace(role="company_admin"),
        is_platform_admin=False,
    )
    loan = SimpleNamespace(id=loan_id, company_id=tenant, borrower_id=borrower_id)
    terms = {"principal": "1000.00", "rate": "20.00"}
    digest = hashlib.sha256(json.dumps(
        terms, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    contract = SimpleNamespace(
        id=contract_id, loan_id=loan_id, company_id=tenant,
        borrower_id=borrower_id, version=3, status="signed",
        locked_at=datetime.now(timezone.utc),
        borrower_signed_at=datetime.now(timezone.utc),
        company_signed_at=datetime.now(timezone.utc),
        pdf_file_id=file_id, terms_snapshot=terms, contract_hash=digest,
    )
    file = SimpleNamespace(
        id=file_id, company_id=tenant, linked_entity_type="loan_contract",
        linked_entity_id=str(contract_id), category="loan_contract",
        is_deleted=False, is_confidential=True, visibility="company",
        scan_status="clean", mime_type="application/pdf",
        checksum_sha256=hashlib.sha256(PDF).hexdigest(),
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [contract, file]
    return db, context, loan, contract, file


def _load(db, context, loan, contract):
    return load_signed_loan_contract_pdf(
        db=db, context=context, loan_id=loan.id,
        contract_id=contract.id, contract_version=3,
    )


@pytest.fixture(autouse=True)
def loan_gate():
    with patch("services.document_issuance_contract_source.require_tenant_roles"), patch(
        "services.document_issuance_contract_source.require_authorized_loan_document_record"
    ) as guard:
        guard.side_effect = lambda *, db, context, loan_id: _loans[loan_id]
        yield


_loans = {}


def _allow(loan):
    _loans.clear()
    _loans[loan.id] = loan


def test_verified_signed_contract_returns_exact_current_pdf():
    db, context, loan, contract, file = _case()
    _allow(loan)
    with patch("services.document_issuance_contract_source.read_file_bytes",
               return_value=PDF) as read:
        result = _load(db, context, loan, contract)
    assert result.contract_id == contract.id
    assert result.contract_version == 3
    assert result.file_id == file.id
    assert result.sha256_hex == hashlib.sha256(PDF).hexdigest()
    assert result.terms_sha256_hex == contract.contract_hash
    read.assert_called_once_with(file)
    db.commit.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("status", "draft"), ("locked_at", None),
    ("borrower_signed_at", None), ("company_signed_at", None),
    ("version", 4), ("company_id", uuid4()),
    ("loan_id", uuid4()), ("borrower_id", uuid4()),
    ("pdf_file_id", None), ("terms_snapshot", {}),
    ("contract_hash", "0" * 64),
])
def test_invalid_contract_never_reads_pdf(field, value):
    db, context, loan, contract, file = _case()
    _allow(loan)
    setattr(contract, field, value)
    with patch("services.document_issuance_contract_source.read_file_bytes") as read:
        with pytest.raises(PermissionError):
            _load(db, context, loan, contract)
    read.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("company_id", uuid4()), ("linked_entity_type", "client_company_loan"),
    ("linked_entity_id", "wrong"), ("category", "general"),
    ("is_deleted", True), ("is_confidential", False),
    ("visibility", "public"), ("scan_status", "validated"),
    ("mime_type", "image/png"), ("checksum_sha256", "0" * 64),
])
def test_invalid_current_pdf_metadata_or_digest_denied(field, value):
    db, context, loan, contract, file = _case()
    _allow(loan)
    setattr(file, field, value)
    with patch("services.document_issuance_contract_source.read_file_bytes",
               return_value=PDF) as read:
        with pytest.raises(PermissionError):
            _load(db, context, loan, contract)


def test_missing_contract_rejected():
    db, context, loan, contract, _ = _case()
    _allow(loan)
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None]
    with pytest.raises(PermissionError):
        _load(db, context, loan, contract)


def test_contract_version_bool_rejected_before_loan_query():
    db, context, loan, contract, _ = _case()
    with pytest.raises(ValueError):
        load_signed_loan_contract_pdf(
            db=db, context=context, loan_id=loan.id,
            contract_id=contract.id, contract_version=True,
        )
    db.query.assert_not_called()


def test_signed_contract_staging_uses_generator_file_bytes():
    db, context, loan, contract, _ = _case()
    _allow(loan)
    store = object()
    with patch("services.document_issuance_contract_source.read_file_bytes",
               return_value=PDF), patch(
        "services.document_issuance_immutable_staging.stage_locked_document_candidate",
        return_value="locked-candidate",
    ) as stage:
        result = stage_signed_loan_contract_pdf(
            db=db, context=context, loan_id=loan.id, contract_id=contract.id,
            contract_version=3, trusted_verification_origin="https://verify.example.test",
            store=store, stamp_configuration_version=2,
        )
    assert result == "locked-candidate"
    stage.assert_called_once_with(
        context=context, source_pdf=PDF,
        trusted_verification_origin="https://verify.example.test",
        store=store, db=db, stamp_configuration_version=2,
    )
