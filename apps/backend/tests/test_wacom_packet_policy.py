"""Only eligible reviewed evidence may be archived exactly once."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from services.wacom_packet_policy import packet_blockers


def setup():
    now=datetime.now(timezone.utc)
    company, intent_id, contract_id = uuid4(), uuid4(), uuid4()
    intent=SimpleNamespace(
        id=intent_id, company_id=company, contract_id=contract_id,
        status="verified", operator_user_id=uuid4(), review_by=uuid4(),
        document_sha256="a"*64, evidence_sha256="b"*64,
        binding_sha256="c"*64,
    )
    approval=SimpleNamespace(
        company_id=company, intent_id=intent_id, contract_id=contract_id,
        status="approved", requested_by=uuid4(), decided_by=uuid4(), consumed_at=None,
        decision_reference="TEST-APPROVAL",
        expires_at=now+timedelta(minutes=3),
        document_sha256="a"*64, evidence_sha256="b"*64,
        binding_sha256="c"*64,
    )
    return intent, approval, uuid4()


def test_matching_unused_approved_packet_is_eligible():
    i,a,e=setup()
    assert packet_blockers(approval=a,intent=i,executor_id=e)==[]


def test_consumed_or_rejected_approval_is_denied():
    i,a,e=setup()
    a.status="consumed"
    a.consumed_at=datetime.now(timezone.utc)
    assert "approval_unavailable" in packet_blockers(approval=a,intent=i,executor_id=e)
    a.status="rejected"
    assert "approval_unavailable" in packet_blockers(approval=a,intent=i,executor_id=e)


def test_expired_approval_is_denied():
    i,a,e=setup()
    a.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert "approval_expired" in packet_blockers(approval=a,intent=i,executor_id=e)


def test_cross_company_and_different_document_are_denied():
    i,a,e=setup()
    a.company_id=uuid4()
    a.document_sha256="0"*64
    reasons=packet_blockers(approval=a,intent=i,executor_id=e)
    assert "approval_scope_changed" in reasons
    assert "approved_document_changed" in reasons


def test_capture_operator_or_reviewer_cannot_archive():
    i,a,_=setup()
    for actor in [i.operator_user_id,i.review_by]:
        assert "independent_archiver_required" in packet_blockers(
            approval=a,intent=i,executor_id=actor,
        )


def test_unverified_evidence_denied():
    i,a,e=setup()
    i.status="rejected"
    assert "reviewed_evidence_unavailable" in packet_blockers(
        approval=a,intent=i,executor_id=e,
    )


def test_archive_feature_defaults_off(monkeypatch):
    from fastapi import HTTPException
    from routers.wacom_finalization_packets import _gate
    monkeypatch.delenv("LOANHUB_WACOM_PACKET_ARCHIVE_ENABLED", raising=False)
    try:
        _gate()
    except HTTPException as exc:
        assert exc.status_code==503
    else:
        raise AssertionError("Packet archival accidentally enabled")


def test_archive_does_not_mutate_loan_contract():
    import inspect
    from routers.wacom_finalization_packets import archive_approved_evidence
    src=inspect.getsource(archive_approved_evidence)
    assert "borrower_signed_at =" not in src
    assert "company_signed_at =" not in src
    assert "contract.status =" not in src


def test_requester_or_approver_cannot_archive_their_own_approval():
    intent, approval, _ = setup()
    for actor in (approval.requested_by, approval.decided_by):
        assert "independent_archiver_required" in packet_blockers(
            approval=approval, intent=intent, executor_id=actor,
        )


def test_distinct_archiver_remains_eligible():
    intent, approval, _ = setup()
    actor = uuid4()
    assert actor not in {
        intent.operator_user_id, intent.review_by,
        approval.requested_by, approval.decided_by,
    }
    assert packet_blockers(approval=approval, intent=intent, executor_id=actor) == []
