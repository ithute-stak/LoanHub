# Profile

Source folder for the `profile` area of LoanHub.

## Location

```text
apps/frontend/app/(dashboard)/borrower/profile
```

## Engineering rules

- Keep tenant and branch access checks on the backend.
- Do not commit secrets, generated caches or runtime uploads.
- Keep user-facing labels readable; database UUIDs are internal identifiers.
- Add or update tests and documentation when behaviour changes.
- Run the project validation workflow before deployment.

## Related documentation

See the repository root `README.md` and the files in `docs/` for architecture, security, roles and deployment.
