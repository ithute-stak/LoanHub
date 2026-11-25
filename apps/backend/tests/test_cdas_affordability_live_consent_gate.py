"""Fail-closed live CDAS consent gate: no provider or reservations on unreviewed evidence."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from routers import cdas_government_employees as module
from services.cdas_affordability_consent_policy import PURPOSE


class Query:
    def __init__(self, items):
        self.items = items
    def filter(self, *clauses):
        return self
    def first(self):
        return self.items


class DB:
    def __init__(self, evidence=None, document=None, managed_file=None):
        self.evidence, self.document, self.managed_file = evidence, document, managed_file
    def query(self, model):
        if model is module.CdasAffordabilityConsentEvidence:
            return Query(self.evidence)
        if model is module.BorrowerDocument:
            return Query(self.document)
        if model is module.ManagedFile:
            return Query(self.managed_file)
        raise AssertionError("Unexpected query before CDAS consent check")


def context(company):
    return SimpleNamespace(company_id=company, user=SimpleNamespace(id=uuid4()))


def approved(*, company, borrower, reviewer, reference="CONSENT-001"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        company_id=company, borrower_id=borrower, employee_number="EMP-100",
        reference=reference, purpose=PURPOSE, status="approved",
        document_id=uuid4(), managed_file_id=uuid4(), document_sha256="a" * 64,
        verified_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
        verified_by_user_id=reviewer,
        borrower_authorization_confirmed=True,
    )


@pytest.mark.asyncio
async def test_unreviewed_recorded_assessment_blocks_before_reservation(monkeypatch):
    company, borrower = uuid4(), uuid4()
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    def forbidden_reserve(*args, **kwargs):
        raise AssertionError("Consent must be checked before any reservation")
    monkeypatch.setattr(module, "reserve_affordability_attempt", forbidden_reserve)
    async def forbidden_provider(*args, **kwargs):
        raise AssertionError("Unreviewed consent must not contact CDAS")
    monkeypatch.setattr(module, "preview_government_employee_affordability", forbidden_provider)
    payload = module.RecordedGovernmentEmployeeAffordabilityRequest(
        borrower_id=borrower, employee_number="EMP-100",
        proposed_monthly_installment="150.00",
        idempotency_key="consent-block-001", consent_evidence_reference="CONSENT-001",
        authorisation_confirmed=True,
    )
    with pytest.raises(HTTPException) as blocked:
        await module.create_government_affordability_record(
            payload=payload, context=context(company), db=DB(),
        )
    assert blocked.value.status_code == 409
    assert "consent_evidence_unavailable" in blocked.value.detail["reason_codes"]


@pytest.mark.asyncio
async def test_unreviewed_live_preview_blocks_before_provider(monkeypatch):
    company, borrower = uuid4(), uuid4()
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    def forbidden_provider(*args, **kwargs):
        raise AssertionError("Preview must be consent gated")
    monkeypatch.setattr(module, "get_company_cdas_client", forbidden_provider)
    payload = module.GovernmentEmployeeAffordabilityRequest(
        borrower_id=borrower, employee_number="EMP-100",
        proposed_monthly_installment="150.00",
        authorisation_confirmed=True,
    )
    with pytest.raises(HTTPException) as blocked:
        await module.preview_government_employee_affordability(
            payload=payload, context=context(company), db=DB(),
        )
    assert blocked.value.status_code == 409


def test_approved_consent_must_still_have_borrower_linked_document(monkeypatch):
    company, borrower, reviewer, operator = (uuid4() for _ in range(4))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    with pytest.raises(HTTPException) as blocked:
        module._require_approved_affordability_consent(
            DB(evidence=evidence), company_id=company,
            borrower_id=borrower, employee_number="EMP-100",
            reference="CONSENT-001", operator_user_id=operator,
        )
    assert blocked.value.status_code == 409
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", lambda **kw: "a" * 64)
    good = module._require_approved_affordability_consent(
        DB(evidence=evidence, document=SimpleNamespace(id=evidence.document_id),
           managed_file=SimpleNamespace(id=evidence.managed_file_id)),
        company_id=company, borrower_id=borrower, employee_number="EMP-100",
        reference="CONSENT-001", operator_user_id=operator,
    )
    assert good is evidence


def test_approved_record_cannot_be_used_by_its_own_reviewer():
    company, borrower, reviewer = (uuid4() for _ in range(3))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    with pytest.raises(HTTPException) as blocked:
        module._require_approved_affordability_consent(
            DB(evidence=evidence, document=SimpleNamespace(id=evidence.document_id)),
            company_id=company, borrower_id=borrower,
            employee_number="EMP-100", reference="CONSENT-001",
            operator_user_id=reviewer,
        )
    assert "reviewer_not_independent" in blocked.value.detail["reason_codes"]


def test_expired_approved_evidence_fails_closed():
    company, borrower, reviewer, operator = (uuid4() for _ in range(4))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    evidence.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(HTTPException) as blocked:
        module._require_approved_affordability_consent(
            DB(evidence=evidence, document=SimpleNamespace(id=evidence.document_id)),
            company_id=company, borrower_id=borrower,
            employee_number="EMP-100", reference="CONSENT-001",
            operator_user_id=operator,
        )
    assert "consent_expired" in blocked.value.detail["reason_codes"]


def test_approved_consent_without_managed_file_fails_before_provider(monkeypatch):
    company, borrower, reviewer, operator = (uuid4() for _ in range(4))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    evidence.managed_file_id = None
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("No managed-file read")))
    with pytest.raises(HTTPException) as blocked:
        module._require_approved_affordability_consent(
            DB(evidence=evidence, document=SimpleNamespace(id=evidence.document_id)),
            company_id=company, borrower_id=borrower, employee_number="EMP-100",
            reference="CONSENT-001", operator_user_id=operator,
        )
    assert blocked.value.status_code == 409
    assert "managed-file binding" in str(blocked.value.detail)


def test_approved_consent_file_content_digest_rechecked(monkeypatch):
    company, borrower, reviewer, operator = (uuid4() for _ in range(4))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    def stale_document(**kwargs):
        assert kwargs["expected_digest"] == evidence.document_sha256
        raise HTTPException(status_code=409, detail="Content checksum changed")
    monkeypatch.setattr(module, "verify_managed_cdas_consent_bytes", stale_document)
    with pytest.raises(HTTPException) as blocked:
        module._require_approved_affordability_consent(
            DB(evidence=evidence, document=SimpleNamespace(id=evidence.document_id),
               managed_file=SimpleNamespace(id=evidence.managed_file_id)),
            company_id=company, borrower_id=borrower, employee_number="EMP-100",
            reference="CONSENT-001", operator_user_id=operator,
        )
    assert blocked.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["revoked", "rejected", "pending"])
async def test_nonapproved_live_preview_never_contacts_provider(monkeypatch, status):
    company, borrower, reviewer = (uuid4() for _ in range(3))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    evidence.status = status
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    monkeypatch.setattr(module, "get_company_cdas_client",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            AssertionError("Invalid consent must not contact CDAS")))
    payload = module.GovernmentEmployeeAffordabilityRequest(
        borrower_id=borrower, employee_number="EMP-100",
        proposed_monthly_installment="150.00",
        authorisation_confirmed=True,
        consent_evidence_reference="CONSENT-001",
    )
    with pytest.raises(HTTPException) as blocked:
        await module.preview_government_employee_affordability(
            payload=payload, context=context(company), db=DB(evidence=evidence),
        )
    assert blocked.value.status_code == 409
    assert "consent_not_approved" in blocked.value.detail["reason_codes"]


@pytest.mark.asyncio
async def test_revoked_recorded_assessment_never_reserves_or_contacts_provider(monkeypatch):
    company, borrower, reviewer = (uuid4() for _ in range(3))
    evidence = approved(company=company, borrower=borrower, reviewer=reviewer)
    evidence.status = "revoked"
    monkeypatch.setattr(module, "_require_company_manager", lambda ctx: None)
    monkeypatch.setattr(module, "reserve_affordability_attempt",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            AssertionError("Revoked consent must not reserve an attempt")))
    async def forbidden_preview(*args, **kwargs):
        raise AssertionError("Revoked consent must not contact provider")
    monkeypatch.setattr(module, "preview_government_employee_affordability", forbidden_preview)
    payload = module.RecordedGovernmentEmployeeAffordabilityRequest(
        borrower_id=borrower, employee_number="EMP-100",
        proposed_monthly_installment="150.00",
        idempotency_key="revoked-gate-001",
        consent_evidence_reference="CONSENT-001",
        authorisation_confirmed=True,
    )
    with pytest.raises(HTTPException) as blocked:
        await module.create_government_affordability_record(
            payload=payload, context=context(company), db=DB(evidence=evidence),
        )
    assert blocked.value.status_code == 409
    assert "consent_not_approved" in blocked.value.detail["reason_codes"]
