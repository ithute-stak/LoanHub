# LoanHub Redux Data Center — disabled repository staging

The repository contains a memory-only Redux boundary and a guarded browser bridge. The bridge is **off by default**, requires an explicit build-time pilot flag, and refuses installation unless the server supplies an authenticated complete six-directory snapshot with a durable generation and replay cursor. This document is not authorization to activate the pilot.

## Invariants
- The existing authenticated WebSocket, DB_EVENT invalidation, notifications, HTTP cache, loans, payments and financial operations are unchanged.
- The bridge is disabled by default. Its opt-in requires an explicit `NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED=true` build and a server-enabled, authorized capture generation.
- The slice is memory-only and accepts only server-authorized allowlisted directory fields. No access tokens, bank details, salary figures, loan amounts or financial calculations are persisted.
- Schema/capture and replay PRs are staged separately. Capture defaults off for every company; the bridge cannot become ready until a journal-backed snapshot contract is certified.

## Before enabling
Integrate and review the separately developed offline projection engine, server-authorized snapshot/replay endpoints, transactional PostgreSQL outbox, Redis wake-up transport, cross-branch permission checks, and client-side session lifecycle. Then require:
1. Complete Next.js/FastAPI build and CI.
2. Real PostgreSQL 16 and Redis 7 integration tests, including concurrency and reconnect recovery.
3. Browser tests for logout, branch/company changes, stale responses and no cross-tenant leakage.
4. Security approval and an explicit deployment/rollback plan.

Do not describe the disabled bridge as a working Redux-first deployment.
