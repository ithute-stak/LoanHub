# LoanHub Final Accounting, Expense and Reporting Release

## Release summary

This release turns the separate Accounting and Money & Expenses pages into one responsive company financial workspace. It connects branch treasury activity, loan transactions, expenses, accounting journals, receipts, stored reports and daily headquarters submissions instead of requiring staff to enter the same transaction in several places.

The main company route is:

```text
/company/expense-management
```

The old route remains safe and redirects to the unified page:

```text
/company/accounting → /company/expense-management
```

The Alembic migration head is:

```text
m5d7c9e2a140
```

## 1. Unified accounting and expense workspace

The unified page contains these functional books:

1. Overview
2. Daily money book
3. Opening-balance sources
4. Expense approvals
5. Branch positions
6. Headquarters funding
7. Statements
8. Accounting books
9. Reports and branch-submission PDFs
10. Financial controls

The page is responsive for desktop, tablet and mobile. Wide tables use horizontal scrolling, compact actions wrap on smaller screens, and forms open in branded `CustomDialog` components.

## 2. Redux financial state

The page uses the new `financialOperations` Redux slice to retain the active date, selected branch, daily ledger, payment methods, treasury settings, expense categories, transfers, branch submissions, accounting books and stored reports.

Normal buttons update or refresh only the required state. The module does not use `window.location.reload()`. Full browser navigation is reserved for authentication redirects such as an expired session.

The loader requests accounting and report data only when the active role has permission. This prevents a branch user from losing the whole treasury page because a restricted accounting endpoint returned `403`.

## 3. Repayment-schedule top-up action

The company loan repayment-schedule dialog now displays an **Apply for loan top-up** button for active or defaulted loans.

The button opens the origination form with the borrower and current loan preselected:

```text
/company/origination/new?borrower=<borrower-id>&type=top_up&loan=<loan-id>
```

The top-up workflow continues to use the configured company policy:

- top-ups enabled or disabled
- minimum percentage paid
- minimum paid instalments
- payment-history requirement
- replacement-facility settlement rule
- company-owner exception for an otherwise ineligible borrower

The replacement facility remains:

```text
new facility = old outstanding balance + additional cash requested
```

Only the additional cash paid to the borrower is posted as new money out. The old balance is settled internally and linked in the audit history.

## 4. Daily branch treasury cycle

Each branch has one ledger per business date.

```text
00:01  New financial day opens
16:30  Every still-open branch ledger submits to Headquarters
```

A submission locks the business date and creates a numbered immutable snapshot. An authorised manager may reopen a submitted day with a reason. A correction followed by resubmission creates another sequence rather than overwriting the first record.

The opening balance is calculated from confirmed sources:

```text
previous closing balance
+ owner contributions
+ confirmed Headquarters funding
+ bank float
+ cash float
+ retained funds
+ approved opening adjustments
+ other described sources
```

## 5. Complete transaction tracking

The unified money book records and filters:

### Money in

- loan repayments
- owner contributions
- confirmed branch funding
- other income
- authorised adjustments
- manually verified evidence-based payments

### Money out

- loan disbursements
- top-up cash portions
- operating expenses
- Headquarters funding issued to branches
- refunds
- authorised adjustments and other outflows

Loan repayments and disbursements post into the same operational money book used by the branches, preventing the lending register and expense register from drifting apart.

## 6. Payment methods

The platform recognises these transaction channels:

- Bank
- Swipped
- goLink
- CDAS
- M-Pesa Wallet
- M-Pesa Merchant
- M-Pesa Agent
- EcoCash Wallet
- EcoCash Agent
- EcoCash Merchant
- Cash

These values identify how money moved. They do not claim that a live provider integration occurred. Staff can capture a proof reference, supporting-document location and verification notes for manually verified non-cash transactions.

## 7. Expense management controls

Operating expenses support:

- reusable expense categories
- branch and business date
- payment method
- voucher number
- description
- proof/reference
- supporting-document location
- approval threshold
- pending, approved and rejected states
- maker-checker dual control
- voiding with a mandatory reason
- idempotency protection against repeated clicks

A pending expense does not reduce posted financial balances until it is approved.

## 8. Automatic accounting journals

Normal business transactions create accounting journals automatically. Staff do not have to choose debit and credit accounts for every daily operation.

Supported accounting events include:

- owner contributions
- opening sources
- operating expenses
- manually recorded money in or money out
- loan disbursements
- loan repayments
- interest income
- processing-fee income
- top-up internal settlement
- reversals and voids

Internal transfers between branches are excluded from consolidated company income and expense so the same company money is not counted as revenue.

Loan repayments are split using the stored payment allocations:

```text
cash received
= principal recovery
+ interest income
+ processing fees
+ other allocated charges
```

Principal recovery reduces Loans Receivable; only interest and fees are recognised as income.

## 9. Accounting books

The Accounting Books tab includes:

- net profit, assets, liabilities and equity indicators
- chart of accounts
- general journal
- trial balance
- complete Profit and Loss sections
- complete Balance Sheet sections
- date-range filters
- paginated tables
- manual journal dialog for genuine adjustments

A manual journal supports multiple debit and credit lines and displays the difference while the user works. It cannot be submitted until total debit equals total credit.

## 10. Statements and calculators

The Statements tab supports:

- date-from and date-to filters
- branch filter
- direction filter
- multiple payment-channel checkboxes
- selected-channel totals
- gross money in
- gross money out
- net movement
- opening balance
- expected closing balance
- paginated transaction rows
- printable browser statement
- CSV export

Useful calculators are included where operational decisions need them, including statement totals, selected-channel totals and balanced-journal differences.

## 11. Headquarters submission PDFs

Every manual or automatic daily branch submission generates a detailed PDF and stores it through LoanHub Files.

The PDF contains:

- company, branch and Headquarters details
- business date and submission sequence
- automatic or manual mode
- opening balance
- money in and money out
- expected and declared closing balances
- variance
- payment-channel totals
- expense-category totals
- opening-source totals
- detailed movement rows
- submission notes
- branch and Headquarters signature areas

Reopening and resubmitting produces another permanent PDF sequence. The earlier file remains unchanged.

The Reports & PDFs tab allows authorised users to filter submission history, download a PDF, and regenerate a missing file without altering the financial snapshot.

## 12. Stored reports

Authorised users can generate and retain:

- financial reports
- portfolio reports
- operations reports
- executive reports

Reports include treasury metrics such as:

- opening sources
- owner contributions
- money in, money out and net movement
- operating expenses
- loan collections and disbursements
- latest branch submission counts
- automatic submission counts
- submission variances
- per-channel money in, money out and net totals

Generated PDFs are saved as managed files instead of temporary downloads.

## 13. Supermarket-style receipts

Payment receipts were redesigned for an 80 mm thermal/supermarket layout. A receipt can be printed immediately or downloaded from its managed-file record.

A repayment receipt includes, where applicable:

- company and branch
- receipt number and date
- cashier
- payment method and proof reference
- customer and loan number
- tendered and applied amount
- principal, interest, fee and penalty allocations
- change returned
- amount carried forward
- balance before and after payment
- instalment number, due date and outstanding amount
- verification code
- customer and cashier signature areas

A top-up disbursement receipt distinguishes the old-loan settlement from the actual additional cash paid to the borrower.

## 14. Tables, filters and pagination

High-volume financial tables now have pagination and applicable filters. This includes:

- daily entries
- expense approvals
- statements
- journal entries
- trial balance
- branch submissions
- stored reports

The backend submission endpoint also supports server-side `skip` and `limit` values and returns a total count.

## 15. Roles

Recommended responsibilities:

- **Company Owner** — all-company oversight, controls, owner exceptions, reopening, approvals and reports.
- **Company Administrator** — treasury configuration, categories, accounting and all-branch reporting.
- **Branch Manager** — assigned-branch entries, approvals, submission and authorised reopening.
- **Finance Officer** — entries, proof capture, repayments, disbursements, branch funding and reconciliation.
- **Loan Officer** — loan and top-up application preparation.
- **Risk Manager** — affordability and top-up risk review.
- **Auditor** — read-only accounting, statements, submissions and report files.

Accounting and report tabs are hidden when the active role is not permitted to use their APIs.

## 16. Docker deployment

Two deployment layouts are included.

### Recommended layout

`compose.yaml` runs:

- Next.js on port 3000
- FastAPI on port 8000
- PostgreSQL
- Redis
- one-off Alembic migration service
- maintenance worker

This layout is recommended because the frontend and backend can be restarted and scaled independently.

### One application container

`compose.single-container.yaml` builds the frontend and backend into one application image and exposes both ports:

- 3000 — Next.js
- 8000 — FastAPI

PostgreSQL and Redis remain separate stateful services for safe backup and recovery.

Persistent volumes retain:

- PostgreSQL data
- Redis data
- receipts
- contracts
- generated reports
- branch-submission PDFs
- other LoanHub managed files

## 17. Installation

Back up PostgreSQL before upgrading.

```bash
cd backend
alembic current
alembic upgrade head
alembic current
```

Expected migration head:

```text
m5d7c9e2a140
```

Frontend development validation:

```bash
cd frontend
rm -rf .next
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm build
pnpm dev
```

Docker:

```bash
cp .env.docker.example .env
mkdir -p secrets
# Generate deployment JWT keys and put them in ./secrets.
docker compose up -d --build
```

One application image:

```bash
docker compose -f compose.single-container.yaml up -d --build
```

## 18. Validation completed

- Backend Python compilation: passed
- SQLAlchemy mapper configuration: passed
- Backend automated tests: **37 passed**
- FastAPI routes: **258**
- Unique FastAPI paths: **205**
- Alembic heads: **1**
- Migration head: **m5d7c9e2a140**
- Full offline upgrade SQL: **4,408 lines**
- Release downgrade SQL: **14 lines**
- TypeScript/TSX source files scanned: **327**
- TypeScript parser diagnostics: **0**
- Missing local `@/` imports: **0**
- Unused imported symbols in the static scan: **0**
- Native browser `alert`, `confirm` and `prompt` calls: **0**
- `window.location.reload()` calls: **0**
- Docker Compose YAML parsing: passed
- Docker startup shell syntax: passed

A complete dependency-aware Next.js production build was not run in the isolated build environment because the uploaded source did not contain `node_modules`, `pnpm` was unavailable, and external package downloads were blocked. Run `pnpm typecheck`, `pnpm lint` and `pnpm build` on the deployment workstation or through the included Docker build before production use.

## 19. Security

Release archives exclude:

- `.env` files
- JWT private/public key files
- virtual environments
- `node_modules`
- `.next`
- Python caches
- media uploads
- production backups

Generate new production secrets for every deployment. Never commit card security codes, payment PINs, wallet PINs, OTPs, database passwords or JWT private keys.
