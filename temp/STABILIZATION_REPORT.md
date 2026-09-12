# LoanHub Stabilization Report

Date: 22 July 2026

## Scope

This release combines the supplied Next.js frontend and FastAPI backend with fixes for type safety, authentication, multi-tenant state, multi-role staff accounts, concurrency, deployment, error handling, and mobile responsiveness.

## Multi-role user model

The final behavior is:

- A person has one `users` account identified by the unique phone/email.
- `company_staff` is the association table between users and companies.
- The unique key is `(user_id, company_id, role)`.
- One user may hold many roles in one or many companies.
- The same role may be held by many users.
- Adding another role by an existing phone/email reuses the existing account instead of creating a duplicate user.
- Staff subscription limits count distinct people, not role rows.
- The first active role becomes primary automatically. Additional roles do not silently replace the primary role.
- Inactive role assignments can be reactivated without creating duplicate rows.
- Role and company selection are tab-scoped, so changing a role in one browser tab does not alter another tab's tenant headers.

## Frontend corrections

- Corrected accounting report calls to pass `AccountingFilters` rather than a raw company ID.
- Corrected nullable assistant actions, support-query form typing, and WebSocket state comparisons.
- Removed the obsolete `/users/` account-creation slice that had no matching backend route.
- Added memory-only access-token handling instead of persistent access-token storage.
- Added coordinated refresh across tabs and isolated impersonation tokens per tab.
- Moved active company, active role, and impersonation state to session storage.
- Added same-origin `/api/v1` proxying and deployment environment examples.
- Added Next.js 16 `proxy.ts` route protection.
- Added global error, global fatal-error, and not-found pages.
- Added stale-request guards to company, staff, and branch Redux slices.
- Remounted application data on user/company/role scope changes to prevent old tenant responses overwriting current data.
- Counted staff as distinct users while retaining role-assignment statistics.
- Updated staff management to add roles to existing accounts and prevent assigning the same role twice.
- Improved dialog sizing, table overflow, global horizontal overflow handling, mobile navigation, visitor registration pages, and small-screen typography/padding.
- Static UI audit found 19 tables; all 19 have horizontal overflow protection.

## Backend corrections

- Removed exposed JWT key files and added safe secret-generation/rotation instructions.
- Added `.gitignore`, `.env.example`, and runtime-secret documentation.
- Reworked company staff creation and assignment to reuse existing users and support many roles.
- Added consistent branch requirements for branch-scoped roles.
- Prevented extra roles from consuming extra staff seats.
- Added primary-role replacement rules when a role is deactivated or deleted.
- Added a database row lock to refresh-token rotation to prevent concurrent reuse.
- Added a PostgreSQL advisory lock to the treasury scheduler so multiple Uvicorn workers cannot run the same cycle concurrently.
- Renamed the misspelled notification model module to `broadcast.py`.
- Marked the circular direct-loan foreign keys for deferred creation to stabilize metadata ordering.
- Replaced deprecated FastAPI startup/shutdown handlers with a lifespan handler.
- Replaced deprecated Pydantic class configuration in affected schemas.
- Added isolated test-secret generation and development test requirements.
- Added multi-role integration tests and API smoke tests.

## Validation results

### Backend

- Python source compilation: PASS
- Pytest: **46 passed**
- Release validator: PASS
- Alembic head: `m5d7c9e2a140`
- SQLAlchemy mappers: 71
- Database tables: 71
- Router modules: 31
- OpenAPI paths: 192
- HTTP operations: 245
- Root endpoint smoke test: PASS
- OpenAPI generation smoke test: PASS
- Anonymous protected-route rejection: PASS
- Real SQLite multi-role assignment integration test: PASS
- Secret-generation script verification: PASS

### Frontend

- Dependency-independent TypeScript semantic check over 332 source files: PASS
- Static responsive table audit: 19/19 wrapped for horizontal scrolling
- Literal frontend/backend API route comparison: no confirmed missing application route after obsolete `/users/` code removal

The real `pnpm typecheck`, `pnpm build`, and `pnpm dev` commands were invoked. In this execution environment they stopped inside Corepack before project loading because DNS access to `registry.npmjs.org` was unavailable and the uploaded archive did not include `node_modules`. The complete output is in `PNPM_EXECUTION_LOG.txt`. This is an environment limitation, not a successful production build claim.

## Remaining runtime verification

A complete end-to-end browser test still requires the normal project runtime:

- installed frontend dependencies,
- PostgreSQL,
- Redis for cross-worker realtime fan-out,
- generated local JWT/encryption secrets,
- applied Alembic migrations,
- and any configured external payment/integration sandboxes.

Use `VALIDATION_RUNBOOK.md` for the exact local commands.
