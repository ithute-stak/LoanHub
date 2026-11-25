"""Offline HTTP contract tests: no production connection or borrower data."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.access_control import get_tenant_context
from routers.batlokoa_new_only_registration_offline import (
    build_offline_certification_router,
)
from services.batlokoa_new_only_registration_command import BatlokoaNewClientReceipt
from services.new_client_registration_idempotency import IdempotencyConflict


def payload():
    return {
        "branch_id": str(uuid4()),
        "first_name": "Synthetic",
        "last_name": "Registration",
        "phone": "59000001",
        "date_of_birth": "1991-05-01",
        "national_id": "SYNTHETIC-TEST-ONLY",
        "gender": "female",
        "district": "Maseru",
        "employment_status": "employed",
        "consent_to_share_profile": True,
        "consent_to_credit_checks": True,
    }


def harness(database_name="registration_cert_sandbox"):
    session_factory = MagicMock()
    db = session_factory.return_value.__enter__.return_value
    db.get_bind.return_value.dialect.name = "postgresql"
    db.execute.return_value.scalar_one.return_value = database_name
    app = FastAPI()
    app.include_router(build_offline_certification_router(
        session_factory=session_factory, fingerprint_secret=b"x" * 48,
    ), prefix="/api/v1")
    app.dependency_overrides[get_tenant_context] = lambda: SimpleNamespace(
        synthetic=True,
    )
    return TestClient(app), session_factory, db


def post(client, body=None, key="synthetic-unique-request-123"):
    return client.post("/api/v1/batlokoa/registration/clients",
                       json=body or payload(),
                       headers={"Idempotency-Key": key})


def test_offline_route_absent_from_production_router():
    from api.v1.router import api_router
    assert all(
        route.path != "/batlokoa/registration/clients"
        for route in api_router.routes
    )


def test_missing_operator_ack_prevents_opening_a_session(monkeypatch):
    monkeypatch.delenv("LOANHUB_REGISTRATION_E2E_ACK", raising=False)
    client, factory, _ = harness()
    with patch(
        "routers.batlokoa_new_only_registration_offline.submit_new_only_client"
    ) as writer:
        response = post(client)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "OFFLINE_CERTIFICATION_UNAVAILABLE"
    factory.assert_not_called()
    writer.assert_not_called()


@pytest.mark.parametrize("db_name", ["loanhub", "loanhub_production", "", None])
def test_production_or_unknown_database_denied(monkeypatch, db_name):
    monkeypatch.setenv(
        "LOANHUB_REGISTRATION_E2E_ACK", "isolated_disposable_database"
    )
    client, factory, db = harness(db_name)
    with patch(
        "routers.batlokoa_new_only_registration_offline.submit_new_only_client"
    ) as writer:
        response = post(client)
    assert response.status_code == 503
    writer.assert_not_called()
    assert db.execute.call_count == 2


def test_full_client_http_receipt_contains_no_personal_data(monkeypatch):
    monkeypatch.setenv(
        "LOANHUB_REGISTRATION_E2E_ACK", "isolated_disposable_database"
    )
    client, factory, db = harness()
    client_id = uuid4()
    with patch(
        "routers.batlokoa_new_only_registration_offline.submit_new_only_client",
        return_value=BatlokoaNewClientReceipt(client_id, False),
    ) as writer:
        response = post(client)
    assert response.status_code == 201
    assert response.json() == {
        "registered": True, "client_account_id": str(client_id),
        "replayed": False,
    }
    assert "SYNTHETIC-TEST-ONLY" not in response.text
    assert writer.call_args.kwargs["payload"].national_id == "SYNTHETIC-TEST-ONLY"
    assert writer.call_args.kwargs["independently_approved_release"] is True
    assert writer.call_args.kwargs["session_factory"] is factory


@pytest.mark.parametrize("failure,expected", [
    (IdempotencyConflict("different request"), 409),
    (ValueError("bad identity"), 422),
    (RuntimeError("SENSITIVE BORROWER SECRET"), 503),
])
def test_http_errors_are_non_disclosing(monkeypatch, failure, expected):
    monkeypatch.setenv(
        "LOANHUB_REGISTRATION_E2E_ACK", "isolated_disposable_database"
    )
    client, _, _ = harness()
    with patch(
        "routers.batlokoa_new_only_registration_offline.submit_new_only_client",
        side_effect=failure,
    ):
        response = post(client)
    assert response.status_code == expected
    assert "SENSITIVE" not in response.text
    assert "BORROWER" not in response.text
    assert "different request" not in response.text


def test_unknown_field_or_bad_key_cannot_reach_writer(monkeypatch):
    monkeypatch.setenv(
        "LOANHUB_REGISTRATION_E2E_ACK", "isolated_disposable_database"
    )
    client, _, _ = harness()
    with patch(
        "routers.batlokoa_new_only_registration_offline.submit_new_only_client"
    ) as writer:
        assert post(client, {**payload(), "approve_production": True}).status_code == 422
        assert post(client, key="short").status_code == 422
        assert post(client, key="forbidden/idempotency/key").status_code == 422
    writer.assert_not_called()
