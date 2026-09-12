# Deployment and Operations

## Docker services

- PostgreSQL 16
- Redis 7
- one-shot Alembic `migrate` service
- FastAPI `api`
- maintenance/midnight worker
- Next.js frontend
- Caddy TLS reverse proxy

## Safe release sequence

1. Back up PostgreSQL and the managed media volume.
2. Stop or drain API/maintenance processes that could lock altered tables.
3. Validate one Alembic head: `f1a9c4e7b620`.
4. Run the dedicated migration service.
5. Start API, maintenance, frontend and Caddy.
6. Verify `/health`, login, tenant selection, chat, files, accounting and reports.
7. Retain the previous release and backup for rollback.

## GitHub to Hostinger

The workflow in `.github/workflows/deploy-hostinger.yml` validates Python, migration SQL, TypeScript, the Next.js build and Compose before SSH deployment. Required GitHub secrets are Hostinger host, port, user, deployment path and SSH private key.

## Operations

- Business timezone: `Africa/Maseru`.
- Midnight reports: daily; weekly on Monday; monthly on day 1; annual on January 1.
- The worker uses a PostgreSQL advisory lock and idempotency checks.
- Back up database and files together because file metadata and encrypted bytes are linked.
