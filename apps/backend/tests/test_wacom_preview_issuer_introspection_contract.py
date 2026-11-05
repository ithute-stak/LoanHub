"""Integration contract for preview ticket issuer and introspection verifier.

Uses an ephemeral test signing key only. No database, network or capture
routes are enabled by these tests.
"""
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import HTTPException

from routers.wacom_connector_introspection import _read_ticket
from services.wacom_preview_ticket import issue_wacom_preview_ticket


def test_issuer_and_introspection_share_verified_scoped_ticket_contract(monkeypatch):
    now = datetime.now(timezone.utc)
    company, operator, contract, session_id, workstation = (uuid4() for _ in range(5))
    contract_hash = "a" * 64
    session = SimpleNamespace(
        id=session_id, company_id=company, operator_user_id=operator,
        contract_id=contract, contract_hash=contract_hash,
        expires_at=now + timedelta(minutes=5), status="created",
        evidence_sha256=None,
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_VERIFY_KEY_B64", base64.b64encode(public).decode("ascii"))
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", "wacom-integrated-test")
    ticket = issue_wacom_preview_ticket(
        signing_key=private, key_id="wacom-integrated-test",
        session=session, authenticated_company_id=company,
        authenticated_operator_id=operator, current_contract_id=contract,
        current_contract_hash=contract_hash, expected_session_id=session_id,
        authorized_workstation_id=workstation, now=now,
    )
    claims = _read_ticket(ticket)
    assert claims["company_id"] == str(company)
    assert claims["operator_id"] == str(operator)
    assert claims["contract_id"] == str(contract)
    assert claims["session_id"] == str(session_id)
    assert claims["workstation_id"] == str(workstation)
    assert claims["purpose"] == "test-preview-only"
    assert claims["exp"] - claims["iat"] <= 30

    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", "other-key")
    with pytest.raises(HTTPException) as error:
        _read_ticket(ticket)
    assert error.value.status_code == 403

    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", "wacom-integrated-test")
    first, middle, signature = ticket.split(".")
    modified = first + "." + ("A" if middle[0] != "A" else "B") + middle[1:] + "." + signature
    with pytest.raises(HTTPException) as error:
        _read_ticket(modified)
    assert error.value.status_code == 403
