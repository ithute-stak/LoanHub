# LoanHub Backend Validation Report

## Release identity

- Corrected backend directory: `loanhub_backend_fixed`
- Final Alembic head: `d4e7b6c1a930`
- Validation date: 2026-07-15

## Defects corrected

1. The inherited audit column `created_by` was overwritten by a chat relationship with the same Python name. The relationship is now `created_by_user`, and the global audit hooks only assign values to mapped scalar columns.
2. The Alembic graph contained competing branches and a removed revision that was already recorded by a database. The graph is now linear and retains `3957062b7c66` as a permanent compatibility marker.
3. Historical data migrations used result-fetching code that failed during offline migration rendering. They now use set-based PostgreSQL SQL.
4. JSONB seed rows used Python dictionaries in `op.bulk_insert`, which failed when rendering SQL. The seed data now uses deterministic SQL literals.
5. Several downgrade functions attempted to drop unnamed foreign keys. The constraints are now explicitly named.
6. The final schema lacked the `loan_requests.selected_offer_id` foreign key. The canonical constraint is restored with `ON DELETE SET NULL`.
7. Legacy index names differed from SQLAlchemy model metadata. A final alignment migration safely normalizes them.
8. Release archives previously contained runtime configuration, keys, caches, a virtual environment, Git data and IDE metadata. The corrected archive excludes these.
9. The project did not include a complete `.env.example` even though the secret-generation workflow expected one. A complete example is now included.
10. Unused imports and related static-quality findings were corrected.

## Automated validation completed

### Python and model validation

- `python -m compileall -q .`: passed
- Ruff static analysis: passed with zero findings
- SQLAlchemy mapper configuration: passed
- SQLAlchemy mappers: 37
- SQLAlchemy tables: 37
- Audit-column/relationship collision scan: passed
- Metadata table sorting with warnings treated as errors: passed

### Route validation

- Router modules registered: 25
- OpenAPI paths: 105
- HTTP operations: 142
- Duplicate method/path combinations: none
- Duplicate OpenAPI operation IDs: none
- Missing router registrations: none detected

A FastAPI TestClient smoke pass exercised 141 operations without authentication. Protected endpoints returned authorization responses, malformed public requests returned validation responses, and no tested route returned an unhandled server error.

### Alembic validation

- Alembic heads: exactly one
- Final head: `d4e7b6c1a930`
- Branch points: none
- Full `base -> head` offline SQL generation: passed
- Full `head -> base` offline SQL generation: passed
- Upgrade SQL parsed by a PostgreSQL SQL parser: 474 statements
- Downgrade SQL parsed by a PostgreSQL SQL parser: 286 statements
- Final migration tables compared with SQLAlchemy metadata: 37 of 37 matched
- Final migration columns compared with SQLAlchemy metadata: matched

### Deployment file validation

- `compose.yaml` parsed successfully
- Services detected: API, Caddy, PostgreSQL, maintenance worker, migration service and Redis
- Shell scripts passed `bash -n`
- ZIP integrity validation: required before release packaging

## Important limitation

A complete migration was not executed against a live PostgreSQL server in this execution environment. Attempts to start a disposable server were blocked by environment-level package/network/runtime limitations. Full upgrade and downgrade SQL rendering, PostgreSQL syntax parsing, metadata comparison, migration graph validation and application import validation all passed.

Run the supplied migration script against a backup or staging PostgreSQL database before production deployment.

## Required local verification

```bash
cp .env.example .env
./scripts/generate_secrets.sh
./scripts/migrate_safely.sh
python scripts/validate_release.py
uvicorn main:app --host 0.0.0.0 --port 8000
```
