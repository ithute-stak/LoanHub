# LoanHub Redux Data Center — disabled repository staging

This commit stages a memory-only Redux boundary and provider entrypoint; **it does not install or activate the offline synchronization engine**.

## Invariants
- The existing authenticated WebSocket, DB_EVENT invalidation, notifications, HTTP cache, loans, payments and financial operations are unchanged.
- The new bridge is hardcoded disabled.
- The new slice stores no client records, financial details, tokens or persisted data; there is no record-bearing install action.
- No database migrations or event-outbox endpoints are installed by this change.

## Before enabling
Integrate and review the separately developed offline projection engine, server-authorized snapshot/replay endpoints, transactional PostgreSQL outbox, Redis wake-up transport, cross-branch permission checks, and client-side session lifecycle. Then require:
1. Complete Next.js/FastAPI build and CI.
2. Real PostgreSQL 16 and Redis 7 integration tests, including concurrency and reconnect recovery.
3. Browser tests for logout, branch/company changes, stale responses and no cross-tenant leakage.
4. Security approval and an explicit deployment/rollback plan.

Do not describe the disabled bridge as a working Redux-first deployment.
