"""Fail-closed contract introspection regression checks."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response

from routers.wacom_connector_introspection import (
    ConnectorPreviewQuery,
    _read_ticket,
    introspect_wacom_preview,
)


def _request(**scope):
    return Request({"type": "http", "method": "POST", "path": "/api/v1/wacom/connector/preview-introspect",
                    "headers": [], **scope})


def test_connector_introspection_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", raising=False)
    with pytest.raises(HTTPException) as exc:
        introspect_wacom_preview(ConnectorPreviewQuery(preview_ticket="a"*64), _request(), Response(), db=None)
    assert exc.value.status_code == 503


def test_client_supplied_header_cannot_fake_workstation(monkeypatch):
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "true")
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/wacom/connector/preview-introspect",
                       "headers": [(b"x-verified-wacom-client-workstation-id", str(uuid4()).encode())]})
    with pytest.raises(HTTPException) as exc:
        introspect_wacom_preview(ConnectorPreviewQuery(preview_ticket="a"*64), request, Response(), db=None)
    assert exc.value.status_code == 403


def test_invalid_ticket_fails_closed(monkeypatch):
    monkeypatch.setenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_WACOM_PREVIEW_VERIFY_KEY_B64", "")
    with pytest.raises(HTTPException) as exc:
        introspect_wacom_preview(
            ConnectorPreviewQuery(preview_ticket="a"*64),
            _request(verified_wacom_client_workstation_id=uuid4()),
            Response(), db=None,
        )
    assert exc.value.status_code == 403


def test_read_ticket_rejects_unsigned_claims(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_PREVIEW_VERIFY_KEY_B64", raising=False)
    with pytest.raises(HTTPException) as exc:
        _read_ticket("a"*64)
    assert exc.value.status_code == 403
