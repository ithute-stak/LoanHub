"""Purpose-specific CDAS consent policy tests (no provider/database contact)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.cdas_affordability_consent_policy import (
    PURPOSE, consent_evidence_blockers,
)


def fixture():
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    company, borrower, reviewer, operator = (uuid4() for _ in range(4))
    evidence = SimpleNamespace(
        company_id=company, borrower_id=borrower,
        employee_number="EMP-001", reference="CONSENT-123",
        purpose=PURPOSE, status="approved", document_id=uuid4(),
        document_sha256="a" * 64, verified_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=20),
        verified_by_user_id=reviewer,
        borrower_authorization_confirmed=True,
    )
    args = dict(
        company_id=company, borrower_id=borrower,
        employee_number="EMP-001", reference="CONSENT-123",
        operator_user_id=operator, now=now,
    )
    return evidence, args


def test_correct_independent_unexpired_evidence_is_eligible():
    evidence, args = fixture()
    assert consent_evidence_blockers(evidence=evidence, **args) == []


def test_missing_or_generic_document_cannot_authorize_cdas():
    evidence, args = fixture()
    assert "consent_evidence_unavailable" in consent_evidence_blockers(evidence=None, **args)
    evidence.purpose = "general_application_document"
    assert "wrong_consent_purpose" in consent_evidence_blockers(evidence=evidence, **args)
    evidence.purpose = PURPOSE
    evidence.document_id = None
    assert "consent_document_missing" in consent_evidence_blockers(evidence=evidence, **args)


def test_wrong_company_borrower_employee_and_reference_rejected():
    evidence, args = fixture()
    args["company_id"] = uuid4()
    args["borrower_id"] = uuid4()
    args["employee_number"] = "EMP-999"
    args["reference"] = "CONSENT-OTHER"
    blockers = consent_evidence_blockers(evidence=evidence, **args)
    assert {"company_mismatch", "borrower_mismatch",
            "employee_number_mismatch", "consent_reference_mismatch"} <= set(blockers)


def test_expired_unreviewed_or_self_approved_evidence_rejected():
    evidence, args = fixture()
    evidence.expires_at = args["now"] - timedelta(seconds=1)
    evidence.verified_by_user_id = args["operator_user_id"]
    evidence.borrower_authorization_confirmed = False
    evidence.status = "pending"
    blockers = consent_evidence_blockers(evidence=evidence, **args)
    assert {"consent_expired", "reviewer_not_independent",
            "borrower_authorization_missing", "consent_not_approved"} <= set(blockers)


def test_naive_timestamps_and_invalid_hash_fail_closed():
    evidence, args = fixture()
    evidence.verified_at = datetime(2026, 11, 19, 12)
    evidence.expires_at = datetime(2026, 12, 19, 12)
    evidence.document_sha256 = "not-a-hash"
    blockers = consent_evidence_blockers(evidence=evidence, **args)
    assert {"consent_verification_unavailable", "consent_expired",
            "document_integrity_unavailable"} <= set(blockers)


def test_revoked_and_rejected_consent_are_ineligible_even_before_expiry():
    for status in ("revoked", "rejected"):
        evidence, args = fixture()
        evidence.status = status
        assert "consent_not_approved" in consent_evidence_blockers(
            evidence=evidence, **args
        )


def test_consent_expires_at_exact_boundary():
    evidence, args = fixture()
    evidence.expires_at = args["now"]
    assert "consent_expired" in consent_evidence_blockers(
        evidence=evidence, **args
    )
    evidence.expires_at = args["now"] + timedelta(microseconds=1)
    assert "consent_expired" not in consent_evidence_blockers(
        evidence=evidence, **args
    )


def test_future_review_timestamp_is_invalid():
    evidence, args = fixture()
    evidence.verified_at = args["now"] + timedelta(seconds=1)
    assert "consent_verification_unavailable" in consent_evidence_blockers(
        evidence=evidence, **args
    )
