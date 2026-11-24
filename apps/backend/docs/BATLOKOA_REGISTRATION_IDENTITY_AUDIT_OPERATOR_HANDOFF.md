# Batlokoa permanent registration — production identity audit handoff

**Status: operator procedure only. No automatic database access, DDL, borrower
repair, registration POST activation or Save Client activation.**

## Purpose

Produce a current, **aggregate-only** registration identity audit from the
approved production database replica or authorized read-only connection.
Historical identifiers and any connection credentials must never enter GitHub
issues, CI logs or chat transcripts.

The implementation already lives in
`apps/backend/scripts/report_identity_index_rollout.py`. The script checks
PostgreSQL, the exact configured audit role, a read-only transaction, collision
counts, index metadata, historical overlaps and linkage triage. Its output is
not a production release approval.

## Prerequisites (operator / DBA)

1. Confirm the exact deployed checkout includes the script and the current
   approved LoanHub release. Work in an operator-only environment; do not run
   this report inside a publicly accessible web request.
2. Have the DBA create or explicitly approve a **read-only PostgreSQL role**
   with least-privilege access to the necessary tables/catalogs. Verify there
   is no DDL or DML permission. A runtime application write credential is **not**
   an acceptable substitute.
3. Load `LOANHUB_IDENTITY_AUDIT_DATABASE_URL` from the approved secret store
   without printing it, pasting it into a command or saving it in shell history.
   Set `LOANHUB_IDENTITY_AUDIT_EXPECTED_ROLE` to the reviewed PostgreSQL role.
4. Obtain explicit approval to run the read-only aggregate audit in the
   selected environment and agree on a protected evidence directory.

## Audit invocation

From `apps/backend` in the authorized environment, with the Python
dependencies installed and the two credential/role environment variables
already provisioned by the operator:

```sh
umask 077
export LOANHUB_IDENTITY_AUDIT_ACK=read_only_identity_audit
python -m scripts.report_identity_index_rollout \
  --output /path/to/approved-private-evidence/identity-audit.json
```

Do not place the actual PostgreSQL URL in the command. The output path must
be a newly created file inside the approved private directory. This command
does not perform an index migration.

If the invocation cannot load the module with `python -m` in the deployed
package layout, the reviewed fallback from `apps/backend` is
`python scripts/report_identity_index_rollout.py --output <new-private-path>`;
do not alter role, transaction or acknowledgment checks to get a result.

## Review the JSON without disclosing private records

Confirm the report contains `checked_at`, `database_role`,
`database_name`, `collision_groups`, `blank_identity_rows`,
`candidate_index_names`, `legacy_cross_source_counts`,
`legacy_linkage_review`, `manual_review_worklist` and
`registration_release_blockers`. Cross-check the actual catalog state.
A fresh aggregate report showing zero normalized collision groups does **not**
clear historical borrower overlaps.

Treat these as **blocking** until independent reviewers document resolutions:

- Any unresolved historical borrower link or passport overlap.
- Missing/invalid identity indexes or unreviewed index predicates.
- Unreviewed normalized identity writers.
- Missing DBA, identity-data-steward, privacy/security, lending/operations,
  Batlokoa business owner, or production change-control approval.
- Any failed full-registration/PostgreSQL, rollback, branch authorization,
  encryption, or external-debt certification.

The report always has `safe_to_execute=false`,
`production_approved=false`, and `registration_enabled=false`.
**Never edit those values to claim readiness.** The separate release assessment
is a documentation gate, not permission to run DDL.

## Next authorized stages (not performed here)

1. Two independent reviewers reconcile unresolved historical groups in a
   private, tenant-scoped workflow. Never automatically merge identities or
   change historical loans/payments/settlements to clear the check.
2. DBA separately reviews the proposed `CREATE UNIQUE INDEX CONCURRENTLY`
   definitions, collision resolution, backup, operational locks, invalid-index
   cleanup, rollback and identity-writer coordination. This procedure is not
   an index installation order.
3. After approved index installation, re-run the audit and verify all four
   actual index definitions, uniqueness, validity and readiness.
4. Only after independent release approval, stage an authenticated synthetic
   POST + independent GET readback test. Keep permanent Save Client disabled
   until the production release decision and smoke test are documented.

Record the audit date, database role, high-level blockers, independent reviewer
sign-offs and approved evidence location in restricted change-control records;
do not copy credentials or customer identifiers into this repository.
