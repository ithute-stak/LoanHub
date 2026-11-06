"""Wacom per-contract saved signature eligibility is strictly read-only."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from routers import contract_email_otp as api


def objects():
    company,borrower,contract_id,signature_id,session_id=(uuid4() for _ in range(5))
    now=datetime.now(timezone.utc)
    contract=SimpleNamespace(
        id=contract_id,borrower_id=borrower,status="draft",
        borrower_signed_at=None,locked_at=None,pdf_file_id=uuid4(),
        contract_hash="a"*64,
    )
    authorization=SimpleNamespace(
        company_id=company,borrower_id=borrower,contract_id=contract_id,
        signature_id=signature_id,session_id=session_id,
        status="authorized",contract_hash="a"*64,
        consumed_at=None,verified_identity_at=now,explicit_consent_at=now,
    )
    signature=SimpleNamespace(
        id=signature_id,company_id=company,borrower_id=borrower,
        status="active",revoked_at=None,reuse_opt_in_at=now,
    )
    session=SimpleNamespace(
        id=session_id,company_id=company,contract_id=contract_id,
        contract_hash="a"*64,status="consented",
        verified_identity_at=now,consent_at=now,expires_at=now+timedelta(minutes=5),
    )
    return company,now,contract,authorization,signature,session


def checks(values):
    company,now,contract,authorization,signature,session=values
    return api._fresh_authorization_checks(
        contract,authorization,signature,session,company_id=company,now=now)


def test_complete_exact_contract_authorization_has_no_preflight_blockers():
    assert checks(objects())==[]


def test_missing_authorization_fails_closed():
    values=list(objects())
    values[3]=None
    assert "contract_authorization_missing" in checks(values)


def test_revoked_signature_never_eligible():
    values=list(objects())
    values[4].status="revoked"
    assert "saved_signature_unavailable_or_revoked" in checks(values)


def test_borrower_or_contract_mismatch_fails_closed():
    values=list(objects())
    values[3].borrower_id=uuid4()
    assert "contract_authorization_invalid" in checks(values)
    values=list(objects())
    values[3].contract_hash="b"*64
    assert "contract_authorization_invalid" in checks(values)


def test_used_authorization_never_eligible():
    values=list(objects())
    values[3].status="used"
    assert "contract_authorization_invalid" in checks(values)


def test_expired_or_cancelled_session_never_eligible():
    values=list(objects())
    values[5].expires_at=values[1]-timedelta(seconds=1)
    assert "signing_session_expired" in checks(values)
    values=list(objects())
    values[5].status="cancelled"
    assert "signing_session_invalid" in checks(values)


def test_existing_signed_document_and_missing_pdf_are_blocked():
    values=list(objects())
    values[2].borrower_signed_at=values[1]
    values[2].pdf_file_id=None
    reasons=checks(values)
    assert "contract_already_completed_or_locked" in reasons
    assert "contract_document_unavailable" in reasons


def test_no_implicit_consent_from_saved_image():
    values=list(objects())
    values[3].explicit_consent_at=None
    assert "contract_authorization_invalid" in checks(values)
    values=list(objects())
    values[5].consent_at=None
    assert "signing_session_invalid" in checks(values)


def test_route_is_registered():
    from api.v1.router import api_router
    paths={route.path for route in api_router.routes}
    assert "/contract-signing/contracts/{contract_id}/pad/use-authorization-status" in paths
