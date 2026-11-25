"""Audit must verify its own PostgreSQL session before reading identities.

Mocks exercise only the connection-level authorization boundary: no
production database, real borrower data, migration or registration route.
"""
from unittest.mock import MagicMock, patch

import pytest

from scripts.report_identity_index_rollout import generate_read_only_report
from services.identity_index_rollout_preflight import IndexRolloutPreflightError


@pytest.mark.parametrize(
    ("actual_role", "session_role", "read_only"),
    [
        ("loanhub_app", "loanhub_app", "on"),  # App credentials aren't audit credentials.
        ("identity_audit", "loanhub_app", "on"),  # SET ROLE is not authentication.
        ("loanhub_app", "identity_audit", "on"),
        ("identity_audit", "identity_audit", "off"),  # Read/write transactions forbidden.
        ("identity_audit", "identity_audit", "ON"),  # Only PostgreSQL's exact 'on' accepted.
    ],
)
def test_identity_audit_rejects_unsafe_session_before_scanning(
    actual_role, session_role, read_only,
):
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.one.return_value = (
        "synthetic_sandbox", actual_role, session_role, read_only
    )
    with (
        patch("scripts.report_identity_index_rollout.create_engine", return_value=engine),
        patch("scripts.report_identity_index_rollout.inspect_index_rollout_preflight") as index_scan,
        patch("scripts.report_identity_index_rollout.inspect_legacy_identity_cross_reference") as legacy_scan,
        patch("scripts.report_identity_index_rollout.inspect_legacy_link_triage") as link_scan,
    ):
        with pytest.raises(
            IndexRolloutPreflightError,
            match="Unexpected database role or writable transaction",
        ):
            generate_read_only_report(
                "postgresql://synthetic-no-network.invalid/synthetic_sandbox",
                expected_role="identity_audit",
            )
    index_scan.assert_not_called()
    legacy_scan.assert_not_called()
    link_scan.assert_not_called()
    engine.dispose.assert_called_once()


def test_identity_audit_requires_explicit_session_transaction_guards():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.one.return_value = (
        "synthetic_sandbox", "wrong_role", "wrong_role", "off"
    )
    with patch(
        "scripts.report_identity_index_rollout.create_engine", return_value=engine
    ):
        with pytest.raises(IndexRolloutPreflightError):
            generate_read_only_report(
                "postgresql://synthetic-no-network.invalid/synthetic_sandbox",
                expected_role="identity_audit",
            )
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert "SET TRANSACTION READ ONLY" in statements
    assert "SET LOCAL statement_timeout = '30000ms'" in statements
    assert any("current_user" in statement and "session_user" in statement
               for statement in statements)
    engine.dispose.assert_called_once()
