"""Non-activating tests for the Batlokoa full-registration command adapter."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from core.access_control import TenantContext
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from services import batlokoa_new_only_registration_command as command


def test_default_release_gate_rejects_before_session_or_writer(monkeypatch):
    open_session = Mock(side_effect=AssertionError("Must never open a session"))
    writer = Mock(side_effect=AssertionError("Must never write"))
    monkeypatch.setattr(command, "create_full_new_client_atomically", writer)
    with pytest.raises(command.BatlokoaRegistrationNotReleased):
        command.submit_new_only_client(
            context=None,
            payload=None,
            idempotency_key="repeated-command-1234",
            fingerprint_secret=b"x" * 32,
            session_factory=open_session,
        )
    writer.assert_not_called()
    open_session.assert_not_called()


def test_explicit_false_gate_is_not_overridden_by_payload(monkeypatch):
    writer = Mock(side_effect=AssertionError("Writer cannot run"))
    monkeypatch.setattr(command, "create_full_new_client_atomically", writer)
    with pytest.raises(command.BatlokoaRegistrationNotReleased):
        command.submit_new_only_client(
            context=None, payload={"independently_approved_release": True},
            idempotency_key="repeated-command-1234",
            fingerprint_secret=b"x" * 32,
            session_factory=lambda: None,
            independently_approved_release=False,
        )
    writer.assert_not_called()


def test_invalid_capture_or_context_never_opens_transaction():
    open_session = Mock(side_effect=AssertionError("Must never open a session"))
    with pytest.raises(ValueError, match="Validated complete"):
        command.submit_new_only_client(
            context=None, payload=None,
            idempotency_key="repeated-command-1234",
            fingerprint_secret=b"x" * 32,
            session_factory=open_session,
            independently_approved_release=True,
        )
    open_session.assert_not_called()


def test_approved_staging_path_binds_tenant_before_writer(monkeypatch):
    from database.models.enums import UserRole
    from services.atomic_new_client_registration import AtomicRegistrationResult
    user_id, company_id, branch_id, account_id = (uuid4() for _ in range(4))
    selected = TenantContext(
        user=SimpleNamespace(id=user_id, is_active=True, role=UserRole.LOAN_OFFICER),
        staff=SimpleNamespace(
            user_id=user_id, company_id=company_id,
            is_active=True, role=UserRole.LOAN_OFFICER,
        ),
        company=None, company_id=company_id,
        branch_id=branch_id, is_platform_admin=False,
    )

    # The real Pydantic contract is checked by the adapter. Construct a valid
    # synthetic instance without customer details ever reaching production.
    from datetime import date
    from database.models.enums import Gender, EmploymentStatus
    payload = FullNewOnlyClientCapture(
        branch_id=branch_id, first_name="Synthetic", last_name="Registration",
        phone="59990001", date_of_birth=date(1991, 1, 1),
        national_id="SYNTHETIC-NOT-REAL-001", gender=Gender.MALE,
        district="Maseru", employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=True, consent_to_credit_checks=True,
    )
    events = []

    class FakeSession:
        def __enter__(self):
            events.append("session_open")
            return self
        def __exit__(self, *args):
            events.append("session_close")

    def bind(db, **kwargs):
        assert kwargs["company_id"] == company_id
        assert kwargs["user_id"] == user_id
        assert kwargs["branch_id"] == branch_id
        assert kwargs["actor_scope"] == "tenant"
        events.append("tenant_bound")

    def writer(db, **kwargs):
        assert kwargs["context"] is selected
        assert kwargs["payload"] is payload
        events.append("atomic_writer")
        return AtomicRegistrationResult(account_id, False)

    monkeypatch.setattr(command, "bind_database_tenant_context", bind)
    monkeypatch.setattr(command, "create_full_new_client_atomically", writer)
    receipt = command.submit_new_only_client(
        context=selected, payload=payload,
        idempotency_key="test-approved-command-1234",
        fingerprint_secret=b"x" * 32,
        session_factory=FakeSession,
        independently_approved_release=True,
    )
    assert receipt.client_account_id == account_id
    assert receipt.replayed is False
    assert events == [
        "session_open", "tenant_bound", "atomic_writer", "session_close",
    ]
