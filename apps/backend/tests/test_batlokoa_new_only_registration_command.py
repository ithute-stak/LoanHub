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
