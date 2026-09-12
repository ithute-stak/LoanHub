# LoanHub Cash-Only Micro Loan Release

## Release purpose

This release changes LoanHub from an electronic-provider payment system into a physical-cash lending and repayment system. M-Pesa, EcoCash and EFT pages, APIs, runtime models and provider services are removed from the active application. Historical database migrations and legacy enum labels remain only so an existing database can be upgraded without losing old audit records.

## Main business flow

1. A borrower creates an online request, or a loan officer opens a borrower account and creates a private internal request.
2. The lender evaluates the request and prepares an offer using the **Micro Loan Method**.
3. An accepted loan receives a unique number in this form:
   `LB-YYYYMMDD-######-COMPANY-NAME`
4. An authorized finance user records the approved amount as **cash out** when the borrower receives physical cash.
5. A finance or collections cashier searches by loan number and records **cash in** repayments.
6. Every repayment is allocated to the oldest unpaid instalment first and updates the loan balance, instalment schedule, cash evidence, journal entries and receipt.
7. Partial payments leave a visible outstanding instalment balance.
8. Overpayments can either be returned as change or carried forward to future instalments.

## Micro Loan Method

For principal `x`, monthly rate `r` and term `n`:

- Increase the running balance by the configured rate.
- For every month except the last, divide the rate-adjusted value by two. One half becomes that cycle's calculation component and the other half is carried into the next cycle.
- In the last month, use the complete rate-adjusted carried balance.
- Add all components and any processing fee.
- Divide the total repayable by the number of months to obtain the standard monthly instalment.
- The last schedule row absorbs any rounding difference so the schedule always equals the total repayable.

Example: `x = M1,000`, `r = 20%`, `n = 3`.

- Month 1 component: `M1,000 × 120% ÷ 2 = M600`
- Month 2 component: `M600 × 120% ÷ 2 = M360`
- Month 3 component: `M360 × 120% = M432`
- Total repayable: `M600 + M360 + M432 = M1,392`
- Monthly instalment: `M1,392 ÷ 3 = M464`

The official calculation is performed by the FastAPI endpoint and reused by the offer form, loan creation and repayment schedule.

## Cash repayment outcomes

### Exact instalment
The tendered amount is fully applied and the current instalment is cleared.

### Partial payment
The tendered amount is applied to the current instalment. LoanHub shows and stores the remaining amount still expected for that instalment.

### Overpayment with change
Only the current instalment outstanding is applied. The extra cash is shown and stored as change returned to the borrower.

### Overpayment carried forward
The extra amount is allocated to the next unpaid instalments until the tendered amount or loan balance is exhausted. Any money above the complete loan balance is returned as change.

## Assisted borrower account opening charge

When a loan officer opens an account for a borrower, LoanHub snapshots the owner's currently configured assisted-opening charge. The charge is accrued against the tenant company. A company owner, company administrator or finance officer can use **Settle charge** in the company client book to record physical cash paid by the company to the platform owner.

The settlement creates:

- company cash-out evidence;
- platform cash-in evidence;
- a company expense journal entry;
- platform fee-revenue journal entry;
- a payment receipt;
- the paid status on the borrower account-opening charge.

## Main active API endpoints

- `POST /api/v1/loans/calculator/micro-loan`
- `GET /api/v1/loans/by-reference/{loan_reference}`
- `POST /api/v1/loans/{loan_id}/cash-disburse`
- `POST /api/v1/loans/cash-repayments/preview`
- `POST /api/v1/loans/cash-repayments`
- `POST /api/v1/loan-requests/{request_id}/cash-service-fee`
- `POST /api/v1/company-clients/{account_id}/cash-opening-fee`

## UI engineering changes

- Application dialogs use the shared LoanHub shadcn/Radix dialog layer.
- Native browser `alert`, `confirm` and `prompt` calls have been removed.
- Form input, select and textarea controls use the project UI components.
- Form submission controls use the shared loading button, including disabled and `aria-busy` behavior.
- Cashier, loans, client book, borrower requests and finance pages use improved LoanHub gradients and responsive cards.
- Official loan calculations are loaded from FastAPI instead of being independently reimplemented in forms.
- Direct state-changing calls were removed from React effect bodies; initial loads are deferred or synchronized through subscriptions.
- Unknown API values are normalized before they are rendered, preventing the reported `unknown` to `ReactNode` type error class.
- Route-level loaders and reusable page skeletons are included for important workspaces.

## Database upgrade

Back up the database, then run from the backend directory:

```bash
alembic current
alembic upgrade head
alembic current
```

Expected Alembic head:

```text
f2c6a8e1d430
```

The migration adds cash transaction evidence, Micro Loan calculation snapshots, the wider loan-number field and cash-only fee-provider defaults.

## Security and deployment

The release archives do not include JWT private/public key files or `.env` files. Generate deployment keys with:

```bash
bash scripts/generate_secrets.sh
```

Create the backend `.env`, apply the migration, create the platform owner using the supplied administration script, and start FastAPI and Next.js according to the project README files.

Do not restore the removed electronic-provider routes unless a later approved product release deliberately reintroduces them.

## Validation performed

- Backend compilation passed.
- `15` backend tests passed.
- SQLAlchemy configured `53` model tables.
- FastAPI registered `201` routes.
- Required cash and Micro Loan endpoints were registered.
- Alembic offline upgrade and downgrade SQL generation passed.
- Alembic head is `f2c6a8e1d430`.
- `310` TypeScript/TSX files parsed with zero syntax diagnostics.
- Local `@/` import resolution passed.
- Frontend electronic-provider references: zero.
- Native browser dialogs: zero.
- Raw form inputs/selects/textareas outside UI primitives: zero.
- Raw submit buttons: zero.
- Direct state/load calls inside React effects: zero in the static engineering scan.
- Requested `unknown`/ReactNode assignability error class: zero in the available type-check output.

A complete dependency-aware Next.js production build was not executed because the uploaded frontend archive did not include installed packages. Run `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm lint` and `pnpm build` in the deployment environment before production release.
