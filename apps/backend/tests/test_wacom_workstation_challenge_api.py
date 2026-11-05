"""Wacom HTTP proof endpoint verifies real Ed25519 signatures; never signs contracts."""
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException, Response

from routers import wacom_workstation_challenges as route
from services.wacom_workstation_proof import WacomWorkstationChallenge, challenge_message


def setup_proof(monkeypatch):
    now = datetime.now(timezone.utc)
    company, operator, contract, session, workstation, enrollment, challenge_id = (uuid4() for _ in range(7))
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw()
    nonce = b"X" * 32
    row = SimpleNamespace(
        id=challenge_id, company_id=company, enrollment_id=enrollment,
        session_id=session, nonce=nonce, consumed_at=None,
        created_at=now - timedelta(seconds=1), expires_at=now + timedelta(seconds=15),
    )
    registry = SimpleNamespace(
        id=enrollment, company_id=company, operator_user_id=operator,
        workstation_id=workstation, ed25519_public_key=public,
        approved_at=now, revoked_at=None, status="active",
    )
    ctx = SimpleNamespace(company_id=company, user=SimpleNamespace(id=operator))
    monkeypatch.setattr(route, "_operator_session", lambda *a, **k: (object(), object()))
    monkeypatch.setattr(route, "load_wacom_preview_ticket_signer",
                        lambda: (Ed25519PrivateKey.generate(), "test-backend"))
    monkeypatch.setattr(route, "_active_enrollment", lambda *a, **k: registry)
    class Query:
        def filter(self, *args):
            return self
        def one_or_none(self):
            return row
    class DB:
        committed = 0
        rolled_back = 0
        def query(self, model):
            return Query()
        def commit(self):
            self.committed += 1
        def rollback(self):
            self.rolled_back += 1
    db = DB()
    signed = WacomWorkstationChallenge(
        id=challenge_id, workstation_id=workstation, session_id=session,
        nonce=base64.urlsafe_b64encode(nonce).decode().rstrip("="),
        issued_at=row.created_at, expires_at=row.expires_at,
    )
    signature = base64.b64encode(key.sign(challenge_message(signed))).decode()
    params = dict(
        contract_id=contract, session_id=session,
        payload=route.WorkstationProofRequest(
            workstation_id=workstation, challenge_id=challenge_id,
            signature_base64=signature,
        ),
        response=Response(), db=db, context=ctx,
    )
    return params, row


def test_proof_route_verifies_signature_and_does_not_enable_capture(monkeypatch):
    params, row = setup_proof(monkeypatch)
    consumed = []
    monkeypatch.setattr(route, "consume_verified_wacom_challenge",
                        lambda db, **kwargs: consumed.append(kwargs) or True)
    result = route.verify_wacom_workstation_proof(**params)
    assert result["workstation_authenticated"] is True
    assert result["capture_enabled"] is False
    assert result["preview_ticket_issued"] is False
    assert result["contract_signed"] is False
    assert len(consumed) == 1
    assert params["db"].committed == 1
    assert params["response"].headers["Cache-Control"] == "no-store"


def test_invalid_proof_does_not_consume(monkeypatch):
    params, row = setup_proof(monkeypatch)
    called = []
    monkeypatch.setattr(route, "consume_verified_wacom_challenge",
                        lambda db, **kwargs: called.append(kwargs) or True)
    params["payload"].signature_base64 = base64.b64encode(b"0" * 64).decode()
    with pytest.raises(HTTPException) as ex:
        route.verify_wacom_workstation_proof(**params)
    assert ex.value.status_code == 403
    assert not called
    assert params["db"].committed == 0


def test_consumed_challenge_cannot_be_reused(monkeypatch):
    params, row = setup_proof(monkeypatch)
    row.consumed_at = datetime.now(timezone.utc)
    with pytest.raises(HTTPException) as ex:
        route.verify_wacom_workstation_proof(**params)
    assert ex.value.status_code == 409
    assert params["db"].committed == 0


def test_challenge_route_refuses_unenrolled_device(monkeypatch):
    params, _ = setup_proof(monkeypatch)
    monkeypatch.setattr(route, "_active_enrollment",
                        lambda *a, **kw: (_ for _ in ()).throw(HTTPException(403, "not enrolled")))
    with pytest.raises(HTTPException) as ex:
        route.create_wacom_workstation_challenge(
            contract_id=params["contract_id"], session_id=params["session_id"],
            payload=route.WorkstationChallengeRequest(workstation_id=params["payload"].workstation_id),
            response=Response(), db=params["db"], context=params["context"],
        )
    assert ex.value.status_code == 403
    assert params["db"].committed == 0


def test_api_router_registers_challenge_and_proof_endpoints():
    from api.v1.router import api_router
    paths = {r.path for r in api_router.routes}
    prefix = "/contract-signing/contracts/{contract_id}/pad/sessions/{session_id}"
    assert prefix + "/workstation-challenges" in paths
    assert prefix + "/workstation-proofs" in paths
