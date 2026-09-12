# Upgrade Playbook for Future Programmers

## 1. Locate the domain

Use the page/API/model catalogs to identify the frontend page, component, API client, backend router, schema, service and model. Do not begin by editing several unrelated files.

## 2. Preserve access control

For every new endpoint, define who can access it, which company is active, whether branch scope applies, and which records ordinary borrowers can see. Enforce this on the backend.

## 3. Decide whether persistence changes

- No persistence change: modify router/schema/service and frontend only.
- Persistence change: modify model and create a named Alembic revision.
- Never regenerate or delete old migrations simply because autogenerate reports a difference.

## 4. Keep retries safe

Use idempotency keys, unique constraints, transaction locks or upsert/requery patterns for payments, report generation, accounting bootstrap and external callbacks.

## 5. Update realtime carefully

Use the shared `RealtimeProvider`; do not open a second WebSocket from a feature provider. Coalesce refreshes and deduplicate notification/message IDs.

## 6. Update files carefully

Use `FormData` without manually forcing `Content-Type`. Reuse `file_service.py`; do not create feature-specific unsafe file writes.

## 7. Update documentation and tests

Add the route/model change to the catalogs, update the role matrix and manual, and include a migration/rollback note.

## 8. Validation sequence

```bash
# Backend
python -m compileall -q .
python scripts/validate_release.py
alembic heads
alembic check
alembic upgrade head --sql > /tmp/upgrade.sql

# Frontend
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm build

# Stack
docker compose config
docker compose run --rm migrate
```

## 9. Stage by affected roles

Test every role that can create, view, approve, reject, pay, report or audit the changed record. Also test an unauthorised role and a user from another tenant/branch.
