import hashlib
from uuid import uuid4
from datetime import datetime, timedelta, timezone

import pytest
from services.wacom_document_policy import (
    IntentIdentity, IntentStatus, consent_digest, require_transition,
    check_valid_until, verify_document_bytes,
)


def sample():
    return IntentIdentity(uuid4(),uuid4(),uuid4(),uuid4(),uuid4(),uuid4(),hashlib.sha256(b"exact PDF").hexdigest(),"v1")


def test_binding_rejects_document_swap():
    a=sample()
    b=IntentIdentity(a.company_id,a.borrower_id,a.contract_id,a.source_file_id,a.operator_user_id,
        a.workstation_id,hashlib.sha256(b"altered PDF").hexdigest(),"v1")
    assert a.binding_sha256()!=b.binding_sha256()


def test_binding_rejects_different_employee_and_pc():
    a=sample()
    changed=IntentIdentity(a.company_id,a.borrower_id,a.contract_id,a.source_file_id,uuid4(),a.workstation_id,a.document_sha256,"v1")
    assert a.binding_sha256()!=changed.binding_sha256()
    changed_pc=IntentIdentity(a.company_id,a.borrower_id,a.contract_id,a.source_file_id,a.operator_user_id,uuid4(),a.document_sha256,"v1")
    assert a.binding_sha256()!=changed_pc.binding_sha256()


def test_binding_deterministic():
    a=sample()
    assert a.binding_sha256()==a.binding_sha256()
    assert len(a.canonical()) > 100


def test_raw_document_must_match_stored_hash():
    a=sample()
    verify_document_bytes(a.document_sha256,b"exact PDF")
    with pytest.raises(ValueError):
        verify_document_bytes(a.document_sha256,b"altered PDF")


def test_consent_explicit_and_document_specific():
    a,b=sample(),sample()
    with pytest.raises(ValueError):
        consent_digest(a.binding_sha256(),"yes","CONSENT-1")
    h=consent_digest(a.binding_sha256(),"I agree to sign this exact document","CONSENT-1")
    assert len(h)==64
    assert h != consent_digest(b.binding_sha256(),"I agree to sign this exact document","CONSENT-1")


def test_no_automatic_signing_transition():
    require_transition(IntentStatus.PREPARED,IntentStatus.CONSENTED)
    require_transition(IntentStatus.CONSENTED,IntentStatus.EVIDENCE_UPLOADED)
    require_transition(IntentStatus.EVIDENCE_UPLOADED,IntentStatus.VERIFIED)
    for source,target in [
        (IntentStatus.PREPARED,IntentStatus.VERIFIED),
        (IntentStatus.CONSENTED,IntentStatus.VERIFIED),
        (IntentStatus.VERIFIED,IntentStatus.CONSENTED),
        (IntentStatus.REJECTED,IntentStatus.VERIFIED),
        (IntentStatus.PREPARED,"signed"),
    ]:
        with pytest.raises(ValueError):
            require_transition(source,target)


def test_expired_consent_refused():
    with pytest.raises(ValueError):
        check_valid_until(datetime.now(timezone.utc)-timedelta(seconds=1))
    check_valid_until(datetime.now(timezone.utc)+timedelta(seconds=15))


def test_binding_rejects_different_source_pdf_record():
    a = sample()
    changed = IntentIdentity(a.company_id, a.borrower_id, a.contract_id, uuid4(),
                             a.operator_user_id, a.workstation_id, a.document_sha256,
                             a.document_version)
    assert changed.binding_sha256() != a.binding_sha256()
