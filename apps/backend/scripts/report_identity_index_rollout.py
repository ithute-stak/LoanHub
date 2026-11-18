"""Operator-only read-only identity migration approval report.

Does not apply migrations, create indexes, repair identities or enable routes.
Requires a deliberately provided DB URL and an explicitly read-only role.
No personal identity values are returned or logged.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services.identity_index_rollout_preflight import (
    inspect_index_rollout_preflight,
    IndexRolloutPreflightError,
)

URL_ENV = "LOANHUB_IDENTITY_AUDIT_DATABASE_URL"
ACK_ENV = "LOANHUB_IDENTITY_AUDIT_ACK"
ACK_VALUE = "read_only_identity_audit"
ROLE_ENV = "LOANHUB_IDENTITY_AUDIT_EXPECTED_ROLE"


def render_approval_report(preflight, *, database_role: str, database_name: str) -> dict:
    """Privacy-safe deterministic manifest; approval is always false."""
    if not database_role or not database_name:
        raise IndexRolloutPreflightError("Audited role and database name required")
    counts = preflight.collision_groups
    blanks = preflight.empty_identity_counts
    if len(counts) != 4 or len(blanks) != 4 or any(
        type(n) is not int or n < 0 for n in counts + blanks
    ):
        raise IndexRolloutPreflightError("Untrustworthy aggregate audit counts")
    return {
        "report_version": 1,
        "checked_at": preflight.checked_at.isoformat(),
        "database_role": database_role,
        "database_name": database_name,
        "collision_groups": dict(zip(
            ("national_id", "passport", "phone", "email"), counts
        )),
        "blank_identity_rows": dict(zip(
            ("national_id", "passport", "phone", "email"), blanks
        )),
        "candidate_index_names": list(preflight.invalid_existing_index_names),
        "requires_manual_legacy_reconciliation": (
            preflight.requires_manual_legacy_reconciliation
        ),
        "operator_review_candidate": preflight.operator_review_candidate,
        "index_statements_for_DBA_review_only": list(
            preflight.proposed_statements
        ),
        "safe_to_execute": False,
        "production_approved": False,
        "registration_enabled": False,
        "manual_approvals_required": [
            "lending_domain_owner",
            "privacy_security",
            "database_administrator",
            "production_change_control",
        ],
        "warning": (
            "Review report only. Does not authorize index creation, data "
            "repair, borrower merging, settlements or registration activation."
        ),
    }


def generate_read_only_report(url: str, *, expected_role: str) -> dict:
    if not isinstance(url, str) or not url:
        raise IndexRolloutPreflightError("Explicit audit database URL required")
    if not expected_role or not expected_role.replace("_", "").isalnum():
        raise IndexRolloutPreflightError("Explicit simple read-only role name required")
    engine = create_engine(url, pool_pre_ping=True, connect_args={
        "options": "-c default_transaction_read_only=on",
    })
    try:
        if engine.dialect.name != "postgresql":
            raise IndexRolloutPreflightError("PostgreSQL required")
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL statement_timeout = '30000ms'"))
                # current_user may differ from session_user under SET ROLE;
                # both must match the explicitly approved credential.
                identity = connection.execute(text("""
                    SELECT current_database(), current_user, session_user,
                           current_setting('transaction_read_only')
                """)).one()
                db_name, role, session_role, read_only = identity
                if (
                    role != expected_role or session_role != expected_role
                    or read_only != "on"
                ):
                    raise IndexRolloutPreflightError(
                        "Unexpected database role or writable transaction")
                with Session(bind=connection) as session:
                    with session.begin():
                        scan = inspect_index_rollout_preflight(session)
                return render_approval_report(
                    scan, database_role=role, database_name=db_name
                )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only aggregate identity migration approval report"
    )
    parser.add_argument(
        "--output", type=Path,
        help="Optional local JSON report path; never prints identity values",
    )
    args = parser.parse_args(argv)
    if os.environ.get(ACK_ENV) != ACK_VALUE:
        parser.error(f"Explicit {ACK_ENV}={ACK_VALUE} required")
    url = os.environ.get(URL_ENV)
    expected_role = os.environ.get(ROLE_ENV)
    if not url or not expected_role:
        parser.error(
            f"Both {URL_ENV} and {ROLE_ENV} must be configured")
    # Never print connection strings or exception traces containing secrets.
    try:
        report = generate_read_only_report(url, expected_role=expected_role)
    except Exception:
        print("Identity audit failed closed; verify read-only role, "
              "database configuration and audit logs.", file=sys.stderr)
        return 2
    json_report = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        if args.output.exists():
            print("Refusing to overwrite an existing report.", file=sys.stderr)
            return 2
        fd = os.open(str(args.output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as output:
            output.write(json_report + "\n")
        print("Read-only identity audit report written.", file=sys.stderr)
    else:
        print(json_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
