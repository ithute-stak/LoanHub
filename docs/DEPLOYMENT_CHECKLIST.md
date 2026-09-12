# Deployment and Migration Checklist

## Do not migrate the only copy of the database

The foundation migration changes existing enums, loan products, offers, subscriptions and accepted-loan tables and creates payment/unlock/schedule tables. First take and verify a PostgreSQL backup.

```bash
pg_dump --format=custom --no-owner --no-privileges loan_db > backups/pre-foundation.dump
```

## Staging validation

```bash
cd backend
alembic current
alembic heads
alembic history
alembic upgrade head
python -m compileall -q .
```

Expected Alembic head:

```text
9f1c2d3e4a5b
```

Check the data before production:

- every company owner has an active company membership;
- every borrower has a person profile;
- accepted requests do not have multiple accepted offers;
- loans reference valid requests/offers/companies/borrowers;
- enum values match the current application release;
- plan seeds and resource limits are acceptable for the business.

## Production configuration

- rotate every previously exposed database password and JWT key;
- generate a new `SECRET_KEY`, Fernet key and callback secret;
- set exact frontend origins in `CORS_ORIGINS`;
- set `PAYMENT_MOCK_MODE=false` only after live adapter testing;
- keep `WEB_CONCURRENCY=1` until WebSocket pub/sub is externalized;
- expose only SSH, 80 and 443;
- do not publish PostgreSQL port 5432 or API port 8000;
- enable automated encrypted backups and test restoration;
- configure DNS before Caddy requests certificates.

## Build commands

```bash
cd backend
docker compose build
docker compose run --rm api alembic heads
docker compose up -d
docker compose ps
docker compose logs -f api maintenance caddy
```

## Frontend verification

```bash
cd frontend
pnpm install
pnpm typecheck
pnpm lint
pnpm build
```

A full frontend dependency install and production build must be completed in the target CI/VPS environment before release.
