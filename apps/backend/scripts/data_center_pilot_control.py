"""Privileged, audited and opt-in Data Center pilot control.

This is NOT an API endpoint and is NOT called by the frontend. The default
command is a read-only dry-run. The operator must supply a separate privileged
connection explicitly via LOANHUB_DC_OPERATOR_DATABASE_URL. Normal application
database credentials MUST NOT be used.

Example dry run (no writes):
  python -m scripts.data_center_pilot_control --action activate \
    --company-id UUID --operator change-manager --approval-ref CR-123

A change requires BOTH --apply and --confirm-company UUID, plus the two labels.
Never embed a database password in the command line.
"""
from __future__ import annotations

import argparse
import os
import sys
from uuid import UUID

from sqlalchemy import create_engine, text

RESOURCE_TABLES = {
    "branches": "company_branches",
    "loanProducts": "loan_products",
    "staff": "company_staff",
    "clients": "company_borrower_accounts",
    "loans": "client_company_loan",
    "payments": "payment_transactions",
}
CAP = 500
MAX_JS_CURSOR = 9007199254740991
EXPECTED_REVISION = "dc20261122002"


class PilotControlBlocked(RuntimeError):
    pass


def validate_request(
    *,
    action: str,
    company_id: UUID,
    confirm_company: UUID | None,
    apply: bool,
    operator: str,
    approval_ref: str,
) -> None:
    if action not in {"activate", "disable"}:
        raise PilotControlBlocked("Unknown pilot transition")
    if not operator.strip() or len(operator) > 120:
        raise PilotControlBlocked("Named operator is required (max 120 characters)")
    if not approval_ref.strip() or len(approval_ref) > 160:
        raise PilotControlBlocked("Approved change reference is required (max 160 characters)")
    if apply and confirm_company != company_id:
        raise PilotControlBlocked("Apply requires exact matching --confirm-company")


def verify_database(connection, company_id: UUID, *, action: str) -> dict:
    row = connection.execute(text("""
        SELECT current_user,
               pg_has_role(current_user, 'loanhub_app', 'MEMBER')
    """)).one()
    if row[0] == "loanhub_app" or row[1]:
        raise PilotControlBlocked("Refusing runtime application database role")
    privileges = connection.execute(text("""
        SELECT has_table_privilege(current_user, 'public.loanhub_dc_capture', 'INSERT,UPDATE'),
               has_table_privilege(current_user, 'public.loanhub_dc_pilot_audit', 'INSERT')
    """)).one()
    if not all(privileges):
        raise PilotControlBlocked("Dedicated operator database privileges required")
    versions = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
    if versions != [EXPECTED_REVISION]:
        raise PilotControlBlocked("Unexpected or multiple Alembic revisions")

    # Serialize transitions for the target company. Never acquire locks on
    # borrowers, loans or payments, and never change any financial tables.
    company = connection.execute(text("""
        SELECT id FROM public.loan_companies
        WHERE id = :company_id AND is_active IS TRUE
        FOR UPDATE
    """), {"company_id": company_id}).one_or_none()
    if company is None:
        raise PilotControlBlocked("Active company not found")

    missing = []
    counts = {}
    for resource, table in RESOURCE_TABLES.items():
        trigger = connection.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgrelid = to_regclass(:table_name)
                  AND tgname = 'loanhub_dc_change_capture'
                  AND tgenabled = 'O' AND NOT tgisinternal
            )
        """), {"table_name": f"public.{table}"}).scalar_one()
        if not trigger:
            missing.append(resource)
        count = int(connection.execute(text(f"""
            SELECT count(*) FROM (
                SELECT 1 FROM public.{table}
                WHERE company_id = :company_id LIMIT :limit
            ) AS bounded_rows
        """), {"company_id": company_id, "limit": CAP + 1}).scalar_one())
        counts[resource] = count
    if missing:
        raise PilotControlBlocked("Missing active capture triggers: " + ", ".join(missing))
    if action == "activate" and any(c > CAP for c in counts.values()):
        raise PilotControlBlocked("A directory exceeds the 500-row snapshot limit")

    capture = connection.execute(text("""
        SELECT enabled, generation FROM public.loanhub_dc_capture
        WHERE company_id = :company_id FOR UPDATE
    """), {"company_id": company_id}).one_or_none()
    if action == "activate" and capture and capture.enabled:
        raise PilotControlBlocked("Capture is already enabled")
    if action == "disable" and (capture is None or not capture.enabled):
        raise PilotControlBlocked("Capture is already disabled")

    cursor = int(connection.execute(text("""
        SELECT cursor FROM public.loanhub_dc_clock
        WHERE company_id = :company_id
    """), {"company_id": company_id}).scalar_one_or_none() or 0)
    stats = connection.execute(text("""
        SELECT count(*), min(cursor), max(cursor) FROM public.loanhub_dc_event
        WHERE company_id = :company_id
    """), {"company_id": company_id}).one()
    event_count, first, last = stats
    if (cursor < 0 or cursor > MAX_JS_CURSOR or event_count != cursor
        or (event_count and (first != 1 or last != cursor))
        or (not event_count and (first is not None or last is not None))):
        raise PilotControlBlocked("Journal cursor is not contiguous")
    return {
        "enabled": bool(capture and capture.enabled),
        "generation": capture.generation if capture else None,
        "cursor": cursor,
        "counts": counts,
    }


def run(args: argparse.Namespace) -> int:
    validate_request(
        action=args.action,
        company_id=args.company_id,
        confirm_company=args.confirm_company,
        apply=args.apply,
        operator=args.operator,
        approval_ref=args.approval_ref,
    )
    database_url = os.environ.get("LOANHUB_DC_OPERATOR_DATABASE_URL", "")
    if not database_url:
        raise PilotControlBlocked("Explicit privileged operator database URL is required")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            if not args.apply:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                # Read-only mode cannot take row locks. Verified dry-run in a
                # separate transaction, with the same SQL checks but no locks.
            state = verify_database(connection, args.company_id, action=args.action)
            print("Company:", str(args.company_id))
            print("Action:", args.action)
            print("Mode:", "APPLY" if args.apply else "DRY RUN")
            print("Current capture:", "enabled" if state["enabled"] else "disabled")
            print("Journal cursor:", state["cursor"])
            for name, count in state["counts"].items():
                print(f"  {name}: {count if count <= CAP else '>500'} records")
            if not args.apply:
                print("DRY RUN PASSED; no configuration was changed")
                return 0

            if args.action == "activate":
                connection.execute(text("""
                    INSERT INTO public.loanhub_dc_capture (company_id, enabled, enabled_at)
                    VALUES (:company_id, true, clock_timestamp())
                    ON CONFLICT (company_id) DO UPDATE
                    SET enabled = true, enabled_at = clock_timestamp()
                """), {"company_id": args.company_id})
            else:
                connection.execute(text("""
                    UPDATE public.loanhub_dc_capture SET enabled = false
                    WHERE company_id = :company_id AND enabled = true
                """), {"company_id": args.company_id})
            updated = connection.execute(text("""
                SELECT enabled, generation FROM public.loanhub_dc_capture
                WHERE company_id = :company_id
            """), {"company_id": args.company_id}).one()
            if bool(updated.enabled) != (args.action == "activate"):
                raise PilotControlBlocked("Capture transition failed to persist")
            if args.action == "activate" and updated.generation == state["generation"]:
                raise PilotControlBlocked("Activation failed to rotate generation")
            connection.execute(text("""
                INSERT INTO public.loanhub_dc_pilot_audit
                    (company_id, action, operator, approval_ref,
                     old_generation, new_generation)
                VALUES (:company_id, :action, :operator, :approval_ref,
                        :previous, :current)
            """), {
                "company_id": args.company_id,
                "action": args.action,
                "operator": args.operator.strip(),
                "approval_ref": args.approval_ref.strip(),
                "previous": state["generation"],
                "current": updated.generation,
            })
            print("Audited pilot transition committed:", args.action)
            print("Generation:", updated.generation)
        return 0
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("activate", "disable"), required=True)
    parser.add_argument("--company-id", type=UUID, required=True)
    parser.add_argument("--confirm-company", type=UUID)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--approval-ref", required=True)
    parser.add_argument("--apply", action="store_true", help="Explicitly mutate capture; default read-only")
    args = parser.parse_args()
    try:
        return run(args)
    except PilotControlBlocked as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        return 1
    except Exception:
        # Never expose the privileged connection string or a SQL exception.
        print("BLOCKED: privileged pilot operation failed safely.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
