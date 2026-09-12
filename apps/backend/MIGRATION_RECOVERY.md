# LoanHub Migration Recovery and Upgrade Guide

## Final migration head

```text
d4e7b6c1a930
```

The corrected migration chain is linear:

```text
6c1f9a7e2d40
  -> 3957062b7c66
  -> 8d2f4a1b7c90
  -> b84d1f2a9c30
  -> d4e7b6c1a930
```

`3957062b7c66` is intentionally retained as a no-op compatibility revision. Do not remove it. Some databases already record that revision.

## Supported current database states

The corrected chain can continue normally when `alembic current` reports any of these revisions:

- `6c1f9a7e2d40`
- `3957062b7c66`
- `8d2f4a1b7c90`
- `b84d1f2a9c30`
- `d4e7b6c1a930`

## Safe upgrade procedure

### 1. Stop services that can hold database locks

```bash
pkill -f "uvicorn main:app" || true
pkill -f "docker/maintenance.py" || true
pkill -f "alembic" || true
```

For Docker:

```bash
docker compose stop api maintenance caddy
```

### 2. Back up PostgreSQL

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  "$DATABASE_URL" \
  > loanhub-before-d4e7b6c1a930.dump
```

### 3. Keep your private runtime files

The corrected release intentionally does not contain `.env` or JWT keys. Preserve your existing secure versions outside the extracted archive, then configure the new release using `.env.example`.

### 4. Inspect the graph

```bash
alembic current
alembic heads
alembic branches
alembic history --verbose
```

Expected:

```text
d4e7b6c1a930 (head)
```

There should be one head and no branch points.

### 5. Run the guarded migration workflow

```bash
chmod +x scripts/migrate_safely.sh
./scripts/migrate_safely.sh
```

The script performs compilation, release validation, head validation, the database upgrade and `alembic check`.

### 6. Verify

```bash
alembic current
alembic heads
alembic check
python scripts/validate_release.py
```

`current` and `heads` must both report:

```text
d4e7b6c1a930
```

### 7. Start the application

```bash
uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-exclude ".venv/**" \
  --reload-exclude "secrets/**"
```

## Do not use these shortcuts

Do not run:

```bash
alembic stamp head
```

Stamping can hide missing schema changes.

Do not create meaningless test migrations:

```bash
alembic revision --autogenerate -m "test"
```

Use:

```bash
alembic check
```

Only create a migration when the reported differences are intentional and have been reviewed.

## If a migration is blocked by another connection

Inspect PostgreSQL sessions:

```sql
SELECT
    pid,
    usename,
    application_name,
    state,
    xact_start,
    wait_event_type,
    wait_event,
    query
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
ORDER BY xact_start NULLS LAST;
```

Stop the API and worker before retrying. Terminate only confirmed stale sessions and never copy a process ID from an old log.
