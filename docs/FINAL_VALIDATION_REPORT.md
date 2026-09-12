# Final Validation Report

## Passed in the artifact environment

- Python compilation
- SQLAlchemy mapper configuration
- Audit-field collision checks
- SQLAlchemy table dependency sorting
- One Alembic head (`f1a9c4e7b620`)
- Complete offline Alembic upgrade SQL generation (2,365 lines)
- Complete offline Alembic downgrade SQL generation (1,046 lines)
- FastAPI OpenAPI generation
- 25 registered router modules
- 108 OpenAPI paths and 145 HTTP operations
- No duplicate method/path or operation ID
- 265 frontend TypeScript/TSX files passed syntax transpilation
- No missing local frontend imports
- Shell-script syntax validation
- Compose and GitHub workflow YAML parsing
- README present in every included source directory
- DOCX rendered successfully
- Final PDF preflight passed: 51 A4 pages, tagged, openable, no JavaScript, no encryption
- Every manual page was visually reviewed through six contact sheets

## Staging requirements

1. Restore a production-like PostgreSQL backup into staging.
2. Run the dedicated migration service.
3. Run `alembic current`, `alembic check` and `python scripts/validate_release.py`.
4. Run `pnpm typecheck`, `pnpm lint` and `pnpm build`.
5. Test all roles, tenant isolation, role switching, chat, voice notes, files, reports, accounting and safe error behaviour.
6. Verify 00:00 Africa/Maseru generation with the maintenance worker.
7. Verify HTTPS/WSS, backups and restore procedures before production.
