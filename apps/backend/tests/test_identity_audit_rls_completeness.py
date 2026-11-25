"""Reject incomplete audited identity visibility before any aggregate scan.

All identities are synthetic; these tests never connect to a database.
"""
from unittest.mock import MagicMock, patch

import pytest

from scripts.report_identity_index_rollout import generate_read_only_report
from services.identity_index_rollout_preflight import IndexRolloutPreflightError


_TABLES = (
    "people", "users", "legacy_loan_captures",
    "borrowers", "company_borrower_accounts",
)


@pytest.mark.parametrize("problem", ["rls", "forced_rls", "missing_table", "duplicate_table"])
def test_identity_audit_refuses_incomplete_table_visibility(problem):
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value

    # Identity is an approved, independently authenticated read-only login.
    connection.execute.return_value.one.return_value = (
        "synthetic_sandbox", "identity_audit", "identity_audit", "on"
    )
    rows = [(name, False, False) for name in _TABLES]
    if problem == "rls":
        rows[0] = ("people", True, False)
    elif problem == "forced_rls":
        rows[1] = ("users", False, True)
    elif problem == "missing_table":
        rows.pop()
    else:
        rows[-1] = ("people", False, False)
    connection.execute.return_value.all.return_value = rows

    with (
        patch("scripts.report_identity_index_rollout.create_engine", return_value=engine),
        patch("scripts.report_identity_index_rollout.inspect_index_rollout_preflight") as index_scan,
        patch("scripts.report_identity_index_rollout.inspect_legacy_identity_cross_reference") as legacy_scan,
        patch("scripts.report_identity_index_rollout.inspect_legacy_link_triage") as link_scan,
    ):
        with pytest.raises(IndexRolloutPreflightError, match="full table visibility"):
            generate_read_only_report(
                "postgresql://synthetic.invalid/synthetic_sandbox",
                expected_role="identity_audit",
            )

    index_scan.assert_not_called()
    legacy_scan.assert_not_called()
    link_scan.assert_not_called()
    engine.dispose.assert_called_once()


def test_identity_audit_reads_catalog_only_inside_read_only_transaction():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.one.return_value = (
        "synthetic_sandbox", "identity_audit", "identity_audit", "on"
    )
    connection.execute.return_value.all.return_value = [
        (name, False, False) for name in _TABLES
    ]
    with (
        patch("scripts.report_identity_index_rollout.create_engine", return_value=engine),
        patch("scripts.report_identity_index_rollout.inspect_index_rollout_preflight") as scan,
        patch("scripts.report_identity_index_rollout.inspect_legacy_identity_cross_reference") as legacy,
        patch("scripts.report_identity_index_rollout.inspect_legacy_link_triage") as triage,
        patch("scripts.report_identity_index_rollout.render_approval_report",
              return_value={"registration_enabled": False, "production_approved": False}) as render,
    ):
        result = generate_read_only_report(
            "postgresql://synthetic.invalid/synthetic_sandbox",
            expected_role="identity_audit",
        )

    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements.index("SET TRANSACTION READ ONLY") < next(
        i for i, value in enumerate(statements) if "pg_class" in value
    )
    assert scan.call_count == legacy.call_count == triage.call_count == 1
    render.assert_called_once()
    assert result["registration_enabled"] is False
    assert result["production_approved"] is False
    engine.dispose.assert_called_once()
