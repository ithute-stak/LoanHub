"""Fail-closed tests for physical Wacom preview-ticket issuance configuration."""
import base64
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.wacom_preview_signing_keys import load_wacom_preview_ticket_signer
from routers.wacom_preview_tickets import PreviewTicketProof


def test_ticket_signer_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_PREVIEW_TICKETS_ENABLED", raising=False)
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_SEED_B64", base64.b64encode(b"x"*32).decode())
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", "key-1")
    with pytest.raises(HTTPException) as error:
        load_wacom_preview_ticket_signer()
    assert error.value.status_code == 503


@pytest.mark.parametrize("seed,kid", [
    ("", "key-1"), ("not base64", "key-1"),
    (base64.b64encode(b"x"*31).decode(), "key-1"),
    (base64.b64encode(b"x"*32).decode(), "../../bad"),
])
def test_ticket_signer_rejects_invalid_configuration(monkeypatch, seed, kid):
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_TICKETS_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_SEED_B64", seed)
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", kid)
    with pytest.raises(HTTPException) as error:
        load_wacom_preview_ticket_signer()
    assert error.value.status_code == 503


def test_ticket_signer_accepts_canonical_private_seed(monkeypatch):
    seed=b"z"*32
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_TICKETS_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_SEED_B64", base64.b64encode(seed).decode())
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID", "wacom-preview-v1")
    signer, kid = load_wacom_preview_ticket_signer()
    assert isinstance(signer, Ed25519PrivateKey)
    assert kid == "wacom-preview-v1"
    signed=signer.sign(b"test")
    signer.public_key().verify(signed, b"test")


def test_preview_ticket_endpoint_requires_scoped_proof_not_anonymous_capture():
    from api.v1.router import api_router
    from routers.wacom_preview_tickets import authorize_wacom_preview_ticket
    routes = [
        r for r in api_router.routes
        if r.path.endswith("/pad/sessions/{session_id}/preview-tickets")
    ]
    assert len(routes) == 1
    assert routes[0].endpoint is authorize_wacom_preview_ticket
    assert "POST" in routes[0].methods
    assert "GET" not in routes[0].methods
    assert set(PreviewTicketProof.model_fields) == {
        "workstation_id", "challenge_id", "signature_base64",
    }


def test_ticket_route_fails_before_database_access_when_disabled(monkeypatch):
    from routers.wacom_preview_tickets import authorize_wacom_preview_ticket
    monkeypatch.delenv("LOANHUB_WACOM_PREVIEW_TICKETS_ENABLED", raising=False)
    class NeverDB:
        def query(self, *_):
            raise AssertionError("database cannot be reached with feature disabled")
    with pytest.raises(HTTPException) as error:
        authorize_wacom_preview_ticket(
            contract_id=uuid4(), session_id=uuid4(),
            payload=PreviewTicketProof(
                workstation_id=uuid4(), challenge_id=uuid4(),
                signature_base64=base64.b64encode(b"a"*64).decode(),
            ),
            response=Response(), db=NeverDB(), context=None,
        )
    assert error.value.status_code == 503
