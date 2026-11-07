# Phase 36 — Isolated PostgreSQL idempotency reservation core

This phase introduces an **inactive** PostgreSQL reservation core, with
fail-closed unit tests and concurrency tests on a disposable database.

## Files

- `apps/backend/services/batlokoa_reservation_store.py`: standalone
  SQLAlchemy Core `MetaData` (NOT LoanHub `Base.metadata`), validated
  `ReservationRequest` and atomic insert-or-classify.
- `apps/backend/tests/test_batlokoa_reservation_store.py`: strict disabled,
  cross-company, amount, duplicate and no-commit tests.
- `apps/backend/tests/test_batlokoa_reservation_postgres.py`: unique-schema
  PostgreSQL integration tests for same-key concurrency, conflicting
  requests, tenant key partition and transaction rollback.
- `.github/workflows/batlokoa-reservation-postgres.yml`: disposable
  PostgreSQL 16 GitHub Actions suite; no production credentials or hosts.

## Transaction contract

`reserve_in_existing_transaction` requires an explicit `enabled=True`
argument, caller-owned open transaction and trusted company identifier.
It performs `INSERT ... ON CONFLICT (company_id, idempotency_key) DO NOTHING
RETURNING id`. A conflict reads the existing row `FOR UPDATE` and
classifies SAME_REQUEST vs CONFLICT using loan, borrower, amount, currency
and fingerprint. A fresh key in another company is distinct.

It NEVER commits or rolls back. Rollback and retries are the caller's
responsibility. Callers must not treat this as a payment authorization.

## Deployment guardrails

This module **is not imported into any API/router or production worker**,
the table is **not in LoanHub's mapped Base registry**, and **no Alembic
migration is added**. Production service requests cannot use this write path.
The actual direct Vodacom M-PESA integration, provider credentials and
shortcode 38542 remain untouched.

Before a real schema installation, independently design and approve:

- Row-level security with authenticated tenant context and least-privilege
  database roles (not merely caller-controlled session variables).
- Foreign-key integrity between company, borrower and loan, including
  composite tenant ownership checks.
- Immutable, auditable reservation state history and lifecycle transitions.
- Retention policy, key expiry and collision behavior.
- Approved mandate, principal/interest/charge allocation and legal policies.
- A fully transactional financial ledger and reconciled provider responses.
- Backups, forward-only migrations, rollback, deployment monitoring and
  independent DBA/security/financial review.

Passing the disposable CI suite certifies only this isolated primitive.
It does not make this feature, live collection or payout production ready.
