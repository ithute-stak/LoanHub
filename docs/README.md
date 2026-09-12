# LoanHub v1.0 Documentation Pack

This package is the v1.0 product, operations and developer handover for LoanHub, developed and maintained by Ithute Solutions.

## Main deliverables

- `LoanHub_v1.0_Product_and_Operations_Guide.pdf/.docx` - user-facing product description and role guide.
- `LoanHub_v1.0_Technical_Architecture_and_Developer_Handover.pdf/.docx` - programmer and operations handover.
- `assets/ui/` - illustrative v1.0 UI views based on the implemented navigation and modules.
- `assets/diagrams/` - PNG, SVG and Graphviz sources for system and workflow diagrams.
- `catalogs/` - machine-readable API, model, route, migration and environment catalogs.
- `code_snippets/` - source files selected for future maintainers.
- `LOANHUB_ITHUTEPAYBRIDGE_HANDOVER.md` - cross-system payment integration, security, reconciliation and go-live runbook.

## Baseline

- Product release: LoanHub v1.0
- Latest Alembic head: `f1a9c4e7b620`
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis
- Frontend: Next.js 16, React 19, TypeScript, Redux Toolkit, Tailwind CSS
- Deployment: Docker Compose with Caddy, PostgreSQL, Redis, migration service, API, maintenance worker and frontend
- Business timezone: Africa/Maseru

## Important production boundaries

Live M-Pesa and EcoCash settlement still requires official provider onboarding, current credentials, callback verification, transaction enquiry, reversal and certification. Automatic email delivery of scheduled reports and enterprise malware scanning/object storage are also deployment integrations rather than fully completed provider services.
