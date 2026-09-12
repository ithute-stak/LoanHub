# LoanHub Enterprise Credit Origination Release

## Purpose

This release adds an independent Compuloan-style credit-origination workflow to LoanHub. It is designed around LoanHub's own architecture and UI. It does not copy proprietary source code or screens.

## Included modules

- Company-configured duplicate-loan and affordability policy.
- One-active-loan and open-application enforcement with row locking at approval time.
- Seven-step origination form for application terms, KYC, employment/income, expenses/debts, banking, affordability and submission.
- Secure KYC evidence uploads through the existing managed-file service.
- Versioned affordability assessments using verified income, expenses, debt obligations, living-cost buffers, dependant allowances, DTI and instalment-to-income limits.
- Agreed repayment day and first-instalment date.
- Automatic LoanHub Micro Loan Method preview and server-side calculation.
- Manager override audit fields.
- Loan contract PDF generation, borrower/company signature records and contract lock.
- Contract-required cash-disbursement control.
- Optional provider configuration boundaries for Experian, M-Pesa, DebiCheck, SMS and email.
- Manual bureau and cash-first fallbacks.
- Tokenized-card support only. Full card numbers, CVV/CVC and PIN are intentionally not stored.

## Main frontend routes

- `/company/origination`
- `/company/origination/new`
- `/company/contracts`
- `/company/direct-lending`
- `/company/loans`
- `/company/cashier`

## Main API namespace

`/api/v1/origination`

Key operations include policy management, borrower financial profiles, duplicate checks, application creation, affordability assessment, manager override, submission, contract generation/signing and integration configuration.

## Database migration

Run:

```bash
alembic upgrade head
```

Expected head:

```text
h7c2a9d4e810
```

## Security notes

- KYC file references are validated against the active company and the `kyc` file category.
- Bank account numbers and provider tokens are encrypted.
- API responses contain only masked bank-account information.
- Card CVV/CVC, PIN and raw PAN are rejected by design.
- Provider credentials are encrypted and never returned by configuration endpoints.
- Live external integrations are disabled until provider-specific approved adapters are completed and tested.

## Validation performed

- 29 backend tests passed.
- Python compilation passed.
- SQLAlchemy mapper configuration passed with 63 tables.
- FastAPI imported with 222 routes, including 18 origination routes.
- Alembic has one head and generated PostgreSQL upgrade SQL successfully.
- 312 TypeScript/TSX source files passed syntax parsing.
- Local `@/` import scan reported zero missing modules.
- Added origination frontend files reported zero unused imports in static analysis.

A dependency-aware Next.js build must still be run locally after `pnpm install` because external npm package downloads are unavailable in the build environment used for this release.
