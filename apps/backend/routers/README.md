# Routers

FastAPI endpoint modules. Every router must be registered in api/v1/router.py.

## Location

```text
apps/backend/routers
```

## Engineering rules

- Keep tenant and branch access checks on the backend.
- Do not commit secrets, generated caches or runtime uploads.
- Keep user-facing labels readable; database UUIDs are internal identifiers.
- Add or update tests and documentation when behaviour changes.
- Run the project validation workflow before deployment.

## Related documentation

See the repository root `README.md` and the files in `docs/` for architecture, security, roles and deployment.
