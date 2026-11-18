# Phase 79 — Identity uniqueness migration approval report

This package is a **read-only operator assessment**, not a migration tool.
Phases 77–78 passed CI and are merged, including real concurrent index
build/failed-build cleanup in disposable PostgreSQL. That does not certify
actual production data or activate registration.

## Run against an approved reporting database

The organization must create an approved, genuinely **read-only** PostgreSQL
role with SELECT privileges on only the necessary identity tables and catalog
metadata. Use a separate reporting snapshot or a specifically approved
operational read-only session. Never use an administrative writer credential.

Example (environment variables should be injected securely, not saved in
shell history, scripts or chat):

```bash
cd apps/backend
export LOANHUB_IDENTITY_AUDIT_DATABASE_URL="<approved read-only PostgreSQL DSN>"
export LOANHUB_IDENTITY_AUDIT_EXPECTED_ROLE="identity_audit_reader"
export LOANHUB_IDENTITY_AUDIT_ACK="read_only_identity_audit"
python3 scripts/report_identity_index_rollout.py --output ./identity-index-review.json
```

The script verifies the connected DB user and session user are exactly the
approved role. It explicitly sets its transaction `READ ONLY` and a
30-second statement timeout. It cannot issue DDL, commit registrations or
change an existing identity.

The JSON report contains aggregate normalized collision-group counts,
whitespace-only identity counts, existing-index readiness names, and fixed
proposed `CREATE UNIQUE INDEX CONCURRENTLY` statements **as text only**.
It never emits national ID, passport, phone or email values.

A report is always:
- `safe_to_execute: false`
- `production_approved: false`
- `registration_enabled: false`

Even a zero-collision report merely signals a candidate for independent
review. It is not permission to create indexes.

## Required manual change controls

1. Confirm the reporting snapshot's date, tenant coverage, data integrity
   and suitable privacy restrictions.
2. Review blank identity values, normalized duplicates and legitimate shared
   historic client references. There is no automatic record merge or delete.
3. Audit identity-writing processes (assisted client registration, legacy
   import, borrower signup, staff/borrower changes) for uniqueness
   compatibility and race conditions.
4. Review PostgreSQL collation, exact expressions, partial indexes, DDL
   timeouts, workload and failed invalid-index cleanup.
5. Rehearse an approved migration with backup, monitoring and rollback in
   isolated production-like staging.
6. Obtain written approvals from lending-domain, information-security/privacy,
   DBA and change-control teams before any production DDL.
7. Separately approve and test the Batlokoa registration endpoint, full
   client form capture and operational rollout.

No DDL has been applied to the live database; no customer or loan balances
have been changed by this phase.
