"""Read-only Data Center pilot preflight; NEVER enables capture.

Run inside the approved backend image:
    python -m scripts.data_center_pilot_preflight --company-id <UUID>

Prints aggregate readiness only, not names, personal data, loan balances or
payment details. Exit 0 = eligible for further pilot testing, NOT approval to
switch live customers onto the new Redux data source.
"""
from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlalchemy import text

RESOURCE_TABLES = {
    "branches": "company_branches",
    "loanProducts": "loan_products",
    "staff": "company_staff",
    "clients": "company_borrower_accounts",
    "loans": "client_company_loan",
    "payments": "payment_transactions",
}
SNAPSHOT_CAP = 500
EXPECTED_REVISION = "dc20261122002"
JS_CURSOR_MAX = 9007199254740991


def classify_readiness(
    *,
    revision: str,
    schema_complete: bool,
    triggers_present: dict[str, bool],
    counts: dict[str, int],
    capture_enabled: bool,
    generation_valid: bool,
    cursor: int,
    event_count: int,
    earliest_cursor: int | None,
    latest_cursor: int | None,
) -> list[str]:
    blockers: list[str] = []
    if revision != EXPECTED_REVISION:
        blockers.append("Journal migration is not the installed database revision")
    if not schema_complete:
        blockers.append("Journal schema is incomplete")
    if not all(triggers_present.get(k, False) for k in RESOURCE_TABLES):
        blockers.append("One or more source-table capture triggers are missing")
    for resource in RESOURCE_TABLES:
        count = counts.get(resource, SNAPSHOT_CAP + 1)
        if count > SNAPSHOT_CAP:
            blockers.append(f"{resource} exceeds snapshot cap ({SNAPSHOT_CAP})")
        if count < 0:
            blockers.append(f"{resource} count could not be verified")
    if not capture_enabled:
        blockers.append("Company capture is disabled (expected until approved pilot)")
    if not generation_valid:
        blockers.append("Company capture generation is missing")
    if cursor < 0 or cursor > JS_CURSOR_MAX:
        blockers.append("Journal cursor cannot be represented by browser")
    if event_count != cursor:
        blockers.append("Journal count does not match transaction cursor")
    if event_count:
        if earliest_cursor != 1 or latest_cursor != cursor:
            blockers.append("Journal cursor gap or invalid initial sequence")
    elif earliest_cursor is not None or latest_cursor is not None:
        blockers.append("Empty journal has inconsistent bounds")
    return blockers


def run(company_id: UUID) -> int:
    from database.session import engine

    tables = ("loanhub_dc_capture", "loanhub_dc_clock", "loanhub_dc_event")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("""
                SELECT set_config('loanhub.company_id', :company_id, true)
            """), {"company_id": str(company_id)})
            connection.execute(text("""
                SELECT set_config('loanhub.actor_scope', 'tenant', true)
            """))
            connection.execute(text("""
                SELECT set_config('loanhub.role', 'company_owner', true)
            """))
            revision = connection.execute(text("""
                SELECT version_num FROM public.alembic_version
            """)).scalars().all()
            installed = revision[0] if len(revision) == 1 else "<multiple-or-none>"
            schema = connection.execute(text("""
                SELECT to_regclass('public.loanhub_dc_capture') IS NOT NULL,
                       to_regclass('public.loanhub_dc_clock') IS NOT NULL,
                       to_regclass('public.loanhub_dc_event') IS NOT NULL
            """)).one()
            schema_complete = all(schema)
            triggers: dict[str, bool] = {}
            counts: dict[str, int] = {}
            for kind, table_name in RESOURCE_TABLES.items():
                triggers[kind] = bool(connection.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_trigger
                        WHERE tgrelid = to_regclass(:table_name)
                          AND tgname = 'loanhub_dc_change_capture'
                          AND NOT tgisinternal
                    )
                """), {"table_name": f"public.{table_name}"}).scalar_one())
                # Bounded row count: do not scan every borrower or loan merely
                # to determine if the 500-row pilot is possible.
                counts[kind] = int(connection.execute(text(f"""
                    SELECT count(*) FROM (
                        SELECT 1 FROM public.{table_name}
                        WHERE company_id = :company_id LIMIT :max_rows
                    ) AS bounded_rows
                """), {
                    "company_id": company_id,
                    "max_rows": SNAPSHOT_CAP + 1,
                }).scalar_one())

            capture_enabled = False
            generation_valid = False
            cursor = 0
            event_count = 0
            earliest: int | None = None
            latest: int | None = None
            if schema_complete:
                capture = connection.execute(text("""
                    SELECT enabled, generation FROM public.loanhub_dc_capture
                    WHERE company_id = :company_id
                """), {"company_id": company_id}).one_or_none()
                capture_enabled = bool(capture and capture.enabled)
                generation_valid = bool(capture and capture.generation)
                clock = connection.execute(text("""
                    SELECT cursor FROM public.loanhub_dc_clock
                    WHERE company_id = :company_id
                """), {"company_id": company_id}).scalar_one_or_none()
                cursor = int(clock or 0)
                events = connection.execute(text("""
                    SELECT count(*), min(cursor), max(cursor)
                    FROM public.loanhub_dc_event WHERE company_id = :company_id
                """), {"company_id": company_id}).one()
                event_count = int(events[0])
                earliest = int(events[1]) if events[1] is not None else None
                latest = int(events[2]) if events[2] is not None else None

            blockers = classify_readiness(
                revision=installed,
                schema_complete=schema_complete,
                triggers_present=triggers,
                counts=counts,
                capture_enabled=capture_enabled,
                generation_valid=generation_valid,
                cursor=cursor,
                event_count=event_count,
                earliest_cursor=earliest,
                latest_cursor=latest,
            )
    print(f"Data Center read-only preflight: company {company_id}")
    print("Installed migration:", installed)
    for resource in RESOURCE_TABLES:
        displayed = f">{SNAPSHOT_CAP}" if counts[resource] > SNAPSHOT_CAP else str(counts[resource])
        print(f"  {resource}: rows={displayed}, trigger={'yes' if triggers[resource] else 'NO'}")
    print("Capture:", "enabled" if capture_enabled else "disabled")
    print("Journal: cursor=", cursor, " events=", event_count)
    if blockers:
        for blocker in blockers:
            print("BLOCKED:", blocker)
        print("Production Data Center must remain disabled.")
        return 1
    print("PRECHECK PASS: eligible for further controlled browser and permission testing only.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", type=UUID, required=True)
    args = parser.parse_args()
    try:
        return run(args.company_id)
    except Exception:
        # Avoid logging SQLAlchemy connection URLs, database secrets, or the
        # original database exception content into application support logs.
        print("BLOCKED: read-only preflight could not verify database state.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
