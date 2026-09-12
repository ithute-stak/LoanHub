# Versions

Ordered Alembic revisions. Never delete a revision already recorded by a database.

## Location

```text
apps/backend/alembic/versions
```

## Engineering rules

- Keep tenant and branch access checks on the backend.
- Do not commit secrets, generated caches or runtime uploads.
- Keep user-facing labels readable; database UUIDs are internal identifiers.
- Add or update tests and documentation when behaviour changes.
- Run the project validation workflow before deployment.

## Related documentation

See the repository root `README.md` and the files in `docs/` for architecture, security, roles and deployment.
