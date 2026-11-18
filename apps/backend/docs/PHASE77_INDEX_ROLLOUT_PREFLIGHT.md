# Phase 77 — Identity index rollout preflight

A normalized-identity uniqueness migration must not run against production
until a collision report has been reviewed and existing identity writers
have been audited. Phase 77 adds **read-only** inspection of all four
global user/person identity columns, with no personally identifying values.

The service requires a caller-managed PostgreSQL transaction already marked
`READ ONLY`. It reports:

- The number of normalized collision groups per national ID, passport,
  phone and email.
- The number of present-but-blank identities in each column, including
  whitespace-only values which the proposed partial indexes would exclude.
- Present/missing/invalid candidate indexes and exact proposed SQL
  statements for independent database-administrator review.

Every result, even zero collisions, sets `safe_to_execute=False`,
`production_approved=False` and `registration_enabled=False`.
No function in this phase executes DDL, changes a borrower, links an old
identity, creates a loan, or mutates repayment/settlement history.

## Requirements before an approved migration

1. Review and reconcile duplicates without auto-merging or deleting any
   historical client or loan information.
2. Confirm identity normalization, index definitions, collation and partial
   predicates with the database administrator.
3. Audit all existing signup, legacy import, assisted-create and user-edit
   code paths for compatibility with globally unique identities.
4. Perform independent PostgreSQL rollout/rollback rehearsal using an
   explicitly isolated synthetic environment, including invalid concurrent
   index cleanup and locking behavior.
5. Obtain a signed operational change approval and a separate approval
   before enabling Batlokoa staff registration.

Phase 75 real-model tests and Phase 76 verified-staff tests passed in CI;
this does not establish production collision counts or migration readiness.
