# Phase 65 — Read-only normalized identity collision inventory

The internal service `inspect_identity_collisions` scans PostgreSQL for
case-insensitive, whitespace-trimmed values repeated across:
- Global `people.national_id` and `people.passport_number`
- Global `users.phone` and `users.email`
- `legacy_loan_captures.national_id` across all companies, **only as a
  repeated-capture review signal**. Multiple historical loans legitimately
  sharing a borrower's national ID must not be automatically merged or deleted.

The audit returns **aggregate counts only**, not national IDs, passport
numbers, phone numbers, emails or borrower names. No public route or API is
registered. Only a trusted DBA/operator should run it using a read-only
database role against a reviewed staging or reporting snapshot.

## Deployment and security

Do **not** run the audit automatically during production API requests. The
grouping queries may scan large tables and should be measured with
`EXPLAIN (ANALYZE, BUFFERS)` on a suitable staging clone and scheduled for a
quiet maintenance window if production execution is later approved.

Zero repeated groups is not a complete uniqueness proof. It does not detect
all cross-source identity anomalies, malformed documents, historical merges
or races. No migration, unique index or data repair is included. Both
`safe_to_add_unique_indexes` and `can_register_clients` are always false.

Before enabling client creation: collect and independently review collision
evidence using privileged tools with privacy controls; assess every identity
writer; select an approved normalized uniqueness and concurrency strategy;
test migrations and rollback on an isolated Postgres snapshot; perform a
separately authorized production rollout. Do not alter historical loans,
repayments, settlement flags or borrower financial profiles.
