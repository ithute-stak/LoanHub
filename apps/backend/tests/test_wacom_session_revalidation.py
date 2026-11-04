from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.wacom_session_revalidation import current_pad_preview_eligibility


NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
COMPANY, CONTRACT = uuid4(), uuid4()
HASH = "a" * 64


def records():
    contract = SimpleNamespace(
        id=CONTRACT, company_id=COMPANY, contract_hash=HASH,
        borrower_signed_at=None, locked_at=None, status="pending",
        pdf_file_id=uuid4(),
    )
    session = SimpleNamespace(
        contract_id=CONTRACT, company_id=COMPANY,
        contract_hash=HASH, expires_at=NOW + timedelta(minutes=5),
        status="created", evidence_sha256=None,
    )
    return session, contract


def test_valid_candidate_is_preview_eligible_but_never_authorizes_capture():
    session, contract = records()
    assert current_pad_preview_eligibility(session, contract, NOW) == {
        "preview_eligible": True, "preview_blockers": [],
    }


def test_edited_contract_invalidates_existing_session():
    session, contract = records()
    contract.contract_hash = "b" * 64
    result = current_pad_preview_eligibility(session, contract, NOW)
    assert not result["preview_eligible"]
    assert "contract_changed" in result["preview_blockers"]


def test_signed_or_locked_contract_invalidates_existing_session():
    for field, value in (
        ("borrower_signed_at", NOW),
        ("locked_at", NOW),
        ("status", "signed"),
    ):
        session, contract = records()
        setattr(contract, field, value)
        assert not current_pad_preview_eligibility(session, contract, NOW)["preview_eligible"]


def test_rejects_expired_cancelled_evidenced_and_wrong_tenant_sessions():
    for field, value in (
        ("expires_at", NOW),
        ("status", "cancelled"),
        ("status", "captured"),
        ("evidence_sha256", "b" * 64),
        ("company_id", uuid4()),
        ("contract_id", uuid4()),
    ):
        session, contract = records()
        setattr(session, field, value)
        assert not current_pad_preview_eligibility(session, contract, NOW)["preview_eligible"]


def test_fail_closed_on_missing_pdf_invalid_hash_or_naive_expiry():
    for mutation in ("missing_pdf", "bad_hash", "naive_expiry"):
        session, contract = records()
        if mutation == "missing_pdf":
            contract.pdf_file_id = None
        elif mutation == "bad_hash":
            contract.contract_hash = "untrusted"
        else:
            session.expires_at = datetime(2026, 11, 4, 12)
        assert not current_pad_preview_eligibility(session, contract, NOW)["preview_eligible"]
