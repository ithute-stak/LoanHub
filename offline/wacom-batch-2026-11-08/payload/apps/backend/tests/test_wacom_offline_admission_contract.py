"""Offline security acceptance tests for LoanHub Wacom access boundaries.

Run with pytest after applying the bundle to the genuine LoanHub checkout.
These tests do not contact an external service or access customer data.
"""
import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.v1.router import api_router
from routers import wacom_bridge_device_proof as proof
from routers import local_signatures
from services import wacom_bridge_sessions as sessions


def _context(active=True):
    return SimpleNamespace(company_id=uuid4(), user=SimpleNamespace(id=uuid4(),is_active=active),staff=object())


@pytest.mark.parametrize('endpoint', [
    '/local-signatures/me/status',
    '/local-signatures/clients/lookup',
    '/local-signatures/captures',
])
def test_protected_entrypoints_are_guarded(endpoint):
    routes=[r for r in api_router.routes if r.path==endpoint]
    assert routes, f'Missing API route: {endpoint}'
    for route in routes:
        assert '_require_bridge_session' in {d.call.__name__ for d in route.dependant.dependencies}


def test_enforcement_switch_is_explicit_opt_in(monkeypatch):
    for value in ('','true','TRUE','yes','0'):
        monkeypatch.setenv('LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION', value)
        assert not sessions.bridge_enforcement_enabled()
    monkeypatch.setenv('LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION','1')
    assert sessions.bridge_enforcement_enabled()


def test_no_credential_rejected_before_database_lookup():
    with pytest.raises(HTTPException) as exc:
        sessions.authorize_bridge_session(object(),context=_context(),token=None)
    assert exc.value.status_code==403


def test_inactive_employee_fails_before_database_lookup():
    # Fake session token with the correct canonical form.
    token='wb1_'+'A'*43
    with pytest.raises(HTTPException) as exc:
        sessions.authorize_bridge_session(object(),context=_context(False),token=token)
    assert exc.value.status_code==403


def test_proof_uses_locked_workstation_and_assignment_records():
    source=inspect.getsource(proof._eligible_device)
    assert source.count('with_for_update()')>=2
    assert 'WacomWorkstationEnrollment' in source
    assert 'WacomWorkstationOperator' in source


def test_proof_and_capture_do_not_sign_document():
    code=inspect.getsource(proof.verify_bridge_device_proof)
    assert '"contract_signed": False' in code
    code=inspect.getsource(local_signatures.upload_capture)
    assert 'usable_for_signing' in code


def test_new_bridge_session_ttl_is_five_minutes():
    assert sessions.SESSION_TTL == timedelta(minutes=5)
