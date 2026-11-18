# Phase 85 — Full new-client detail staging (internal only)

Phase 84's complete client capture contract has passed GitHub CI and is
merged. Phase 85 begins the **internal profile staging** layer for the new-only
registration transaction, but does not connect it to the live API.

`stage_full_new_only_client_details` is a separate, disabled-by-default
staging helper that accepts a validated full-form request, an internal
`StagedNewClient` reference, and a caller-owned PostgreSQL transaction.
It contains **no commit** and must only be called by a future independently
certified full-registration writer within the same transaction as creating
the identity and company account.

It checks the newly staged company, borrower, branch and actor references
and then persists these additional fields for that new borrower only:

- Person: middle name, marital status, nationality, town/village, address.
- Borrower: employment type, employer, income day, job title, monthly income,
  salary date.
- Bank account: delegates to LoanHub's existing encryption-backed assisted
  bank-capture helper; bank verification is always unverified.
- Existing external loans: delegates to the existing structured external
  debt helper, never to LoanHub loan/repayment/settlement operations.

An email identity, user-supplied login password, employer-group creation,
CDAS payroll, purported verified bank/debt information, unsupported bare
loan-total values and inconsistent structured debts are rejected BEFORE
profile writes. Unknown fields remain rejected by Phase 84's strict
Pydantic model.

## Not yet certified

This helper is **not** production-ready. The next phase must establish that
the account and borrower were **created in the same current transaction**,
connect full staging only after all Phase 81 staff/branch/identity safeguards,
and demonstrate real PostgreSQL rollback for base client + bank + debt rows.
Existing helper semantics around original amounts and settled external debts
also require regression tests before the full writer can be enabled.

Never call this helper on an existing borrower or connect it to the old
assisted-client code, which can relink historical accounts. No registration
endpoint, feature flag, production migration, or existing LoanHub calculator
and loan ledger changes are introduced.
