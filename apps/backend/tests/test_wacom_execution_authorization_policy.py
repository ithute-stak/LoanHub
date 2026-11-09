"""Persistent Wacom authorization policy contract: never sign or mutate."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as R
from uuid import uuid4

import pytest

from services.wacom_execution_authorization_policy import (
    authorization_request_blockers,
    authorization_decision_blockers,
)


def sample():
    now = datetime(2026, 11, 9, 6, tzinfo=timezone.utc)
    company, intent_id, contract, approval_id, packet_id = [uuid4() for _ in range(5)]
    users = [uuid4() for _ in range(7)]
    hashes = dict(document_sha256="a"*64, evidence_sha256="b"*64,
                  binding_sha256="c"*64)
    intent = R(id=intent_id, company_id=company, contract_id=contract,
               status="verified", review_by=users[1], review_at=now,
               operator_user_id=users[0], consent_at=now,
               consent_reference="consented", expires_at=now+timedelta(minutes=5),
               **hashes)
    approval = R(id=approval_id, company_id=company, intent_id=intent_id,
                 contract_id=contract, status="consumed",
                 consumed_at=now, decided_by=users[3], requested_by=users[2],
                 **hashes)
    packet = R(id=packet_id, company_id=company, intent_id=intent_id,
               contract_id=contract, approval_id=approval_id,
               source_sha256=hashes["document_sha256"],
               handwriting_sha256=hashes["evidence_sha256"],
               created_by_user_id=users[4], packet_file_id=uuid4(),
               archived_at=now)
    permit = R(company_id=company, intent_id=intent_id,
               contract_id=contract, packet_id=packet_id,
               requested_by=users[5], requested_at=now,
               authorized_by=None, consumed_at=None, status="pending",
               expires_at=now+timedelta(minutes=2), **hashes)
    return dict(intent=intent, approval=approval, packet=packet,
                authorization=permit, requester_id=users[5],
                approver_id=users[6], now=now)


def request_reasons(v):
    return authorization_request_blockers(
        intent=v["intent"], approval=v["approval"], packet=v["packet"],
        requester_id=v["requester_id"], now=v["now"])


def decision_reasons(v):
    return authorization_decision_blockers(
        intent=v["intent"], approval=v["approval"], packet=v["packet"],
        authorization=v["authorization"], approver_id=v["approver_id"],
        now=v["now"])


def test_clean_synthetic_request_and_decision():
    v = sample()
    assert request_reasons(v) == []
    assert decision_reasons(v) == []


@pytest.mark.parametrize("record,attribute,value,reason", [
    ("intent", "status", "rejected", "review_or_consent_missing"),
    ("intent", "consent_reference", None, "review_or_consent_missing"),
    ("approval", "status", "approved", "archival_approval_unavailable"),
    ("packet", "packet_file_id", None, "packet_unavailable"),
    ("packet", "company_id", uuid4(), "company_mismatch"),
    ("approval", "intent_id", uuid4(), "intent_mismatch"),
    ("packet", "contract_id", uuid4(), "contract_mismatch"),
    ("packet", "approval_id", uuid4(), "packet_approval_mismatch"),
    ("approval", "document_sha256", "d"*64, "document_sha256_approval_changed"),
    ("packet", "source_sha256", "d"*64, "packet_source_changed"),
])
def test_request_fail_closed(record, attribute, value, reason):
    v = sample()
    setattr(v[record], attribute, value)
    assert reason in request_reasons(v)


@pytest.mark.parametrize("attribute,value,reason", [
    ("status", "approved", "authorization_already_closed"),
    ("consumed_at", datetime(2026, 11, 9, tzinfo=timezone.utc), "authorization_already_closed"),
    ("packet_id", uuid4(), "authorization_binding_mismatch"),
    ("document_sha256", "d"*64, "document_sha256_authorization_changed"),
    ("expires_at", datetime(2026, 11, 9, 6, tzinfo=timezone.utc), "authorization_expired"),
])
def test_decision_fail_closed(attribute, value, reason):
    v = sample()
    setattr(v["authorization"], attribute, value)
    assert reason in decision_reasons(v)


def test_rejects_self_approval():
    v = sample()
    v["approver_id"] = v["requester_id"]
    assert "approver_not_independent" in decision_reasons(v)


def test_rejects_archiver_as_requester():
    v = sample()
    v["requester_id"] = v["packet"].created_by_user_id
    assert "requester_not_independent" in request_reasons(v)


def test_rejects_expired_intent():
    v = sample()
    v["intent"].expires_at = v["now"]
    assert "intent_expired" in request_reasons(v)


def test_deny_naive_expiry():
    v = sample()
    v["authorization"].expires_at = datetime(2026, 11, 9, 8)
    assert "authorization_expired" in decision_reasons(v)


def test_only_pure_policy_no_database_signing():
    import inspect
    from services import wacom_execution_authorization_policy as policy
    src = inspect.getsource(policy)
    for forbidden in ("db.commit(", "PdfWriter(", "store_bytes("):
        assert forbidden not in src
