from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
from services.wacom_approval_policy import approval_blockers


def sample():
    company, intent_id, contract_id, operator, reviewer, requester, approver = (uuid4() for _ in range(7))
    intent=SimpleNamespace(id=intent_id,company_id=company,contract_id=contract_id,
                           status="verified",operator_user_id=operator,review_by=reviewer,
                           document_sha256="a"*64,evidence_sha256="b"*64,binding_sha256="c"*64)
    record=SimpleNamespace(company_id=company,intent_id=intent_id,contract_id=contract_id,
                           status="pending",requested_by=requester,decided_by=None,consumed_at=None,
                           document_sha256="a"*64,evidence_sha256="b"*64,binding_sha256="c"*64,
                           expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
    return intent,record,approver


def test_independent_approver_allowed():
    intent,record,approver=sample()
    assert approval_blockers(intent=intent,approval=record,approver_id=approver)==[]


def test_requester_operator_and_reviewer_cannot_approve():
    intent,record,_=sample()
    for actor in (record.requested_by,intent.operator_user_id,intent.review_by):
        assert "independent_approver_required" in approval_blockers(
            intent=intent,approval=record,approver_id=actor)


def test_expiry_and_replay_denied():
    intent,record,approver=sample()
    record.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert "approval_expired" in approval_blockers(intent=intent,approval=record,approver_id=approver)
    record.status="approved"
    assert "approval_already_closed" in approval_blockers(intent=intent,approval=record,approver_id=approver)


def test_tampered_document_and_evidence_denied():
    intent,record,approver=sample()
    record.document_sha256="d"*64
    record.evidence_sha256="e"*64
    blockers=approval_blockers(intent=intent,approval=record,approver_id=approver)
    assert "approval_document_or_evidence_changed" in blockers


def test_cross_company_and_unverified_intent_denied():
    intent,record,approver=sample()
    record.company_id=uuid4()
    intent.status="rejected"
    blockers=approval_blockers(intent=intent,approval=record,approver_id=approver)
    assert "approval_scope_changed" in blockers
    assert "evidence_not_verified" in blockers
