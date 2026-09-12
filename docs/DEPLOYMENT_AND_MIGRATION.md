# Deployment and Migration

## 1. Back up PostgreSQL

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  loan_db \
  > loanhub-before-ithute-marketable.dump
```

Test restoration before relying on the backup.

## 2. Stop database users during schema migration

```bash
docker compose stop api maintenance caddy
```

For a local non-Docker setup, stop Uvicorn and the maintenance worker before running Alembic.

## 3. Configure environment

Copy the example file and use strong secrets:

```bash
cp .env.example .env
```

Important additions:

```dotenv
FILE_STORAGE_PATH=/app/media/uploads
FILE_MAX_UPLOAD_MB=25
BRAND_NAME=Ithute Solutions
BRAND_LOGO_PATH=assets/ithute-solutions-logo.png
```

JWT private/public keys and provider credentials must never be committed to Git.

## 4. Apply migration

Docker:

```bash
docker compose run --rm migrate
```

Local:

```bash
alembic current
alembic heads
alembic upgrade head
alembic current
alembic check
```

Expected head:

```text
f1a9c4e7b620
```

Do not use `alembic stamp head` to bypass a failed migration.

## 5. Start services

```bash
docker compose up -d api maintenance caddy

docker compose ps
docker compose logs -f api maintenance caddy
```

The maintenance service generates due scheduled reports and performs existing lifecycle reconciliation.

## 6. Frontend

```bash
pnpm install
pnpm typecheck
pnpm lint
pnpm build
pnpm start
```

Set the frontend API and WebSocket URLs for the deployed environment.

## 7. Production file storage

The included `media_data` volume is suitable for a single-host deployment and development. For clustered or high-availability production:

1. Replace local disk writes with S3/MinIO-compatible object storage.
2. Keep file metadata and access policy in PostgreSQL.
3. Use short-lived signed download URLs.
4. Enable malware scanning and file-content validation.
5. Configure lifecycle retention, backup and legal-hold policies.

## 8. Report operations

- Keep the maintenance worker running.
- Monitor failed generated reports.
- Review storage consumption.
- Implement email delivery before relying on recipient lists for distribution.

## 9. Accounting readiness

Before production:

- Approve the chart of accounts.
- Confirm payment-to-account mappings.
- Define tax, bad-debt and fee treatment.
- Lock accounting periods where required.
- Restrict posting permissions.
- Reconcile platform and company ledgers with provider statements.

## 10. Live mobile-money integration

Do not enable production M-Pesa or EcoCash branding until official merchant onboarding, sandbox tests, callback verification, reversals, status enquiries, settlement reconciliation and certification are complete.
