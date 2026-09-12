# LoanHub Ithute Marketable Release - Validation Report

Validation date: 2026-07-15

## Backend

- 141 Python source files parsed and compiled successfully.
- SQLAlchemy mapper configuration passed.
- FastAPI application import passed with 148 registered routes using local validation stubs only for the missing Passlib runtime package.
- Alembic has one head: `f1a9c4e7b620`.
- Docker Compose YAML parsed successfully.
- Compose services detected: API, Caddy, PostgreSQL, maintenance, migrate and Redis.
- Branded operational report PDF generation and rendering passed.

## Frontend

- 258 TypeScript and TSX implementation files passed syntax transpilation.
- Static local-import validation found no missing product-code imports.
- `next-env.d.ts` references `./.next/dev/types/routes.d.ts`; this is an expected Next.js-generated file and appears after the local development/build process creates `.next`.
- Ithute Solutions logos are included in `public/` and used by the product shells/dialog branding.

## Documents

- The full user manual contains 44 rendered pages.
- DOCX rendering passed and every page was visually inspected through contact sheets.
- The final PDF was rendered again at 150 DPI with 44 pages and no observed clipping, overlap or broken glyphs.
- The sample operational report was rendered and visually checked; percentages and currency formatting are correct.

## Release hygiene

- No `.env`, PEM, private key or secret-key files are included.
- Backend virtual environments, caches, runtime uploads and source-control metadata are excluded.
- Frontend `node_modules`, `.next`, build caches and local environment files are excluded.
- Only safe `.env.example` files are included.

## Required staging validation

The following could not be completed in this isolated environment and must be run on staging:

- A real PostgreSQL `alembic upgrade head`
- Full integration tests with PostgreSQL and Redis
- `pnpm install`
- `pnpm typecheck`
- `pnpm lint`
- `pnpm build`
- Browser end-to-end tests for all roles
- Live M-Pesa or EcoCash sandbox transactions and certification
- Email delivery for scheduled-report recipients
- S3/MinIO object-storage integration

Do not deploy directly to the only production database. Back up, restore into staging, migrate, verify and then schedule production maintenance.
