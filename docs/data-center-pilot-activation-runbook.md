# LoanHub Data Center — controlled pilot activation gates

**Status:** The Redux bridge build flag is **off** by default and the PostgreSQL company capture table has **no enabled companies** after migration. The Data Center is **not enabled** merely because these pieces exist in `main`.

## 1. Release prerequisites (non-negotiable)

- The exact `main` commit must pass LoanHub CI, including the disposable PostgreSQL migration and tenant-isolation tests.
- Both immutable images must be published successfully by `.github/workflows/release-images.yml`, which waits for CI on **that same commit**.
- Back up production PostgreSQL before deployment. Deploy only using the approved `pull loanhub latest` VPS launcher and verify all health checks and Alembic revision.
- Run this only from the trusted administration terminal; never enter production database secrets in tickets, chats or browsers.

## 2. Read-only pilot readiness inspection

In the approved backend environment (after the journal migration is deployed):

```bash
python -m scripts.data_center_pilot_preflight --company-id '<verified UUID>'
```

The script uses a read-only repeatable-read transaction and reports only aggregate counts, trigger presence, enabled capture state and replay cursor integrity. It cannot enable the feature. A nonzero status is a **blocker**. An ordinary new deployment is expected to report capture **disabled**; this is the desired safe default.

The current consistent snapshot has a **hard cap of 500 rows per resource**. Any larger company must use a future paginated initial snapshot implementation; never truncate a directory and claim readiness.

## 3. Security and browser certification required before any opt-in

Use an isolated, disposable tenant and verified company owner/admin account. Verify:
- Normal loan officers, HR staff, branch-scoped users, borrowers and platform actors cannot access the management snapshot or replay.
- A different company, branch or staff membership never sees the prior session's cached rows.
- A successful initial snapshot has all six buckets under one PostgreSQL repeatable-read snapshot and exact journal generation/cursor.
- Two concurrent write transactions serialize journal cursors in **commit order**; a rolled-back transaction leaves neither its event nor a cursor gap.
- Missing event, invalid generation, stale cursor, 401/403, network outage, delayed response, login/logout, branch switch, tab resume, WebSocket reconnect and replay overflow fail closed.
- The existing loans/payments/settlements/calculator remain authoritative. No Redux directory row ever supplies a financial balance or authorizes a payment.

## 4. Controlled opt-in requires a separate approval and change procedure

Do not switch `loanhub_dc_capture.enabled` for any production company in this runbook. Do not rebuild frontend with `NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED=true` before the above tests and a company-specific approval. Capture is an opt-in database operation and must be paired with an audited, reversible release plan. Only a separately reviewed privileged operation may change it, and the browser must receive a new, consistent snapshot after opt-in.

## 5. Rollback and stop conditions

- If any snapshot is incomplete, journal gap appears, permissions fail, data becomes stale or financial response changes unexpectedly, stop the pilot. Keep the legacy LoanHub flows authoritative.
- The frontend remains off unless explicitly built with the opt-in flag; remove it for a clean rollback.
- Disabling company capture makes new snapshots and replay fail closed; any future re-enable rotates the capture generation. Never carry a cursor across the disabled interval.
- VPS rollback should follow the approved release launcher, retaining the production PostgreSQL backup. Do not manually downgrade a migration that could contain captured events without a reviewed data recovery plan.

**Acceptance:** only a validated pilot with measured cross-screen latency, WebSocket reconnect, authorization isolation and financial invariants can justify general activation.
