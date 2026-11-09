"""A stored Wacom challenge must not turn prior evidence into a signature."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as R
from uuid import uuid4

import pytest
from services.wacom_ceremony_challenge_policy import (
    ceremony_challenge_blockers, challenge_lifetime_blockers,
)


def sample():
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    company, borrower, contract_id, intent_id, authorization_id, candidate_id = [uuid4() for _ in range(6)]
    actors = [uuid4() for _ in range(6)]
    intent = R(id=intent_id, company_id=company, contract_id=contract_id,
               borrower_id=borrower, source_file_id=uuid4(), document_version="1",
               document_sha256="a"*64, operator_user_id=actors[0], review_by=actors[1])
    authorization = R(
        id=authorization_id, company_id=company, intent_id=intent_id,
        contract_id=contract_id, status="approved", consumed_at=None,
        authorized_by=actors[2], requested_by=actors[3],
        expires_at=now+timedelta(seconds=90),
        field_binding_sha256="b"*64,
    )
    receipt = R(
        company_id=company, intent_id=intent_id, contract_id=contract_id,
        authorization_id=authorization_id, executed_file_id=candidate_id,
        executed_pdf_sha256="c"*64, field_binding_sha256="b"*64,
        document_sha256="a"*64, reserved_by=actors[4],
        status="reserved", executed_at=None,
    )
    contract = R(
        id=contract_id, company_id=company, borrower_id=borrower,
        pdf_file_id=intent.source_file_id, version=1, status="draft",
        borrower_signed_at=None, locked_at=None,
    )
    file = R(
        id=candidate_id, company_id=company, checksum_sha256="c"*64,
        is_deleted=False, is_encrypted=True, is_confidential=True,
        scan_status="clean", mime_type="application/pdf",
        category="wacom_execution_candidate",
    )
    return dict(intent=intent, authorization=authorization, receipt=receipt,
                contract=contract, candidate_file=file,
                requesting_user_id=actors[5], existing_challenge=None, now=now)


def blockers(**v):
    return ceremony_challenge_blockers(**v)


def test_eligible_synthetic_challenge_not_a_signature():
    v = sample()
    assert blockers(**v) == []
    assert v["contract"].borrower_signed_at is None


@pytest.mark.parametrize("target,attribute,value,expected", [
    ("authorization","status","consumed","ceremony_not_eligible"),
    ("receipt","status","executed","ceremony_not_eligible"),
    ("receipt","field_binding_sha256","0"*64,"ceremony_hash_mismatch"),
    ("receipt","executed_pdf_sha256","0"*64,"ceremony_hash_mismatch"),
    ("candidate_file","is_encrypted",False,"ceremony_candidate_untrusted"),
    ("candidate_file","is_confidential",False,"ceremony_candidate_untrusted"),
    ("candidate_file","scan_status","pending","ceremony_candidate_untrusted"),
    ("candidate_file","company_id",uuid4(),"tenant_mismatch"),
    ("contract","version",2,"ceremony_reference_mismatch"),
    ("contract","status","signed","contract_already_executed"),
    ("contract","pdf_file_id",uuid4(),"ceremony_reference_mismatch"),
])
def test_rejects_tampering(target,attribute,value,expected):
    v=sample()
    setattr(v[target],attribute,value)
    assert expected in blockers(**v)


def test_rejects_existing_challenge_and_reviewer_reuse():
    v=sample()
    v["existing_challenge"] = R(id=uuid4(),status="expired")
    assert "ceremony_already_created" in blockers(**v)
    v=sample()
    v["requesting_user_id"] = v["authorization"].authorized_by
    assert "ceremony_requester_not_independent" in blockers(**v)


def test_expired_authorization_cannot_issue_new_challenge():
    v = sample()
    v["authorization"].expires_at = v["now"]-timedelta(seconds=1)
    assert "ceremony_not_eligible" in blockers(**v)


def test_two_minute_challenge_is_bound_to_clock():
    now=datetime.now(timezone.utc)
    assert challenge_lifetime_blockers(
        requested_at=now-timedelta(seconds=10), expires_at=now+timedelta(seconds=90), now=now,
    ) == []
    assert "challenge_not_fresh" in challenge_lifetime_blockers(
        requested_at=now-timedelta(minutes=4), expires_at=now+timedelta(minutes=1), now=now,
    )
    assert "challenge_clock_invalid" in challenge_lifetime_blockers(
        requested_at=now.replace(tzinfo=None), expires_at=now+timedelta(seconds=90), now=now,
    )


def test_schema_uniqueness_and_status_requirements():
    from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
    constraints=WacomExecutionCeremonyChallenge.__table__.constraints
    uniques={tuple(sorted(c.columns.keys())) for c in constraints if c.__class__.__name__ == "UniqueConstraint"}
    assert ("company_id","contract_id") in uniques
    assert ("authorization_id",) in uniques
    assert ("receipt_id",) in uniques
    assert ("challenge_sha256",) in uniques


def test_no_execution_mutation_in_model_or_policy():
    import inspect
    from services import wacom_ceremony_challenge_policy
    code = inspect.getsource(wacom_ceremony_challenge_policy)
    for forbidden in ("db.commit(", "borrower_signed_at =", "contract.status =", "store_bytes("):
        assert forbidden not in code
