# LoanHub M-Pesa integration validation

## Completed in the build environment

- Python `compileall`: passed.
- M-Pesa unit tests: 8/8 passed.
- Alembic graph: single head `b8d5e21f9a30`.
- FastAPI OpenAPI generation: 143 paths.
- M-Pesa and Query Centre API operations: 24.
- TypeScript/TSX syntax transpilation: 285 files, zero syntax diagnostics.
- Local `@/` and relative import scan: zero missing imports.
- DOCX testing manual: rendered and visually inspected across 26 pages.
- PDF testing manual: rendered and visually inspected across 26 pages.

## Not completed in this environment

- Full `pnpm typecheck`, lint and Next.js production build: package manager/dependencies were unavailable and registry access was blocked by DNS/network restrictions.
- Live M-Pesa sandbox calls: no company credentials, enabled sandbox products, service-provider code or registered trusted source were available.
- PostgreSQL `alembic upgrade head`: migration was not run against the user's live/staging database.
- Provider certification or production go-live: external Vodacom/organisation process.

Run locally before release:

```bash
cd apps/frontend
pnpm install
pnpm typecheck
pnpm lint
pnpm build

cd ../loan_backend
source .venv/bin/activate
alembic upgrade head
python -m unittest tests.test_mpesa_service -v
```
