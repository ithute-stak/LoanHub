# LoanHub Internal Lending Workflow Release

## Purpose

This release completes the private, cash-based internal lending workflow. A loan officer can open a borrower account, create an internal loan application for that client, and send the application directly to a controlled company decision queue. The request is not broadcast to other lenders.

## User workflow

1. **Loan Officer** opens or selects a borrower at `/company/clients`.
2. The loan officer selects an active loan product, enters the requested amount, term and purpose, and sees the **Micro Loan Method** calculation update automatically.
3. On successful submission, the interface redirects to `/company/direct-lending?application=<id>` and opens the created application.
4. **Risk Manager or Branch Manager** may start and document the review.
5. **Branch Manager, Company Administrator or Company Owner** approves or rejects the application.
6. Approval creates a unique loan number, loan account and repayment schedule.
7. **Finance Officer, Company Administrator or Company Owner** opens `/company/loans` and records the physical cash disbursement.
8. **Finance Officer, Collections Officer, Branch Manager, Company Administrator or Company Owner** receives instalment payments at `/company/cashier`.

## Loan products

Loan products can be created or edited at `/company/products` by a Company Owner or Company Administrator. The same reusable product dialog is available inside the internal application processing page, allowing an authorized manager to create a missing product without abandoning the application.

A product configures:

- Product name and description
- Minimum and maximum principal
- Minimum and maximum term
- Micro Loan Method rate
- Processing fee
- Active/inactive availability

The API now returns controlled validation errors for duplicate names and invalid ranges. Optional or partially migrated billing tables no longer cause loan-product creation to fail with an unexplained HTTP 500; a conservative product limit is used until the billing schema is upgraded.

## Automatic Micro Loan Method calculation

The borrower application and approval forms call the FastAPI calculator after a short debounce. The backend remains the source of truth.

For M1,000 at 20% for three months:

- Month 1 component: M600
- Month 2 component: M360
- Month 3 component: M432
- Total repayable: M1,392
- Monthly instalment: M464

Approval repeats the calculation on the server, creates the instalment schedule and rejects values outside the selected product limits.

## Internal application controls

- Internal applications are tenant-scoped and branch-scoped.
- Loan officers can create and view applications but cannot approve their own work.
- Risk managers can review but cannot approve.
- Branch managers, company administrators and company owners can approve or reject.
- Finance and audit roles can view the queue according to their permissions.
- Database row locking and unique constraints prevent the same application from being converted into more than one loan.
- Review time, reviewer, decision notes, rejection time and rejecting user are stored for audit.

## Dialog and form standardization

All end-user modal workflows use `components/ui/custom-dialog.tsx`, including clients, loan products, direct applications, loans, cashier, finance, billing, role switching, chat, activity logs and system errors. The low-level shadcn dialog primitive remains only as the implementation foundation for `CustomDialog` and the command-palette primitive.

Forms use shadcn inputs, selects, textareas, checkboxes, buttons and loading buttons. API errors are normalized before display. Unknown API values are converted into safe renderable strings instead of being passed directly to React.

## Backend migration

Apply:

```bash
cd backend
alembic upgrade head
alembic current
```

Expected head:

```text
g4d8e1f2a760
```

The migration adds review and decision audit fields to `direct_loan_applications`.

## Validation completed

- Python compilation passed.
- Backend automated tests: **22 passed**.
- FastAPI application imported with **204 routes**.
- Alembic has one head: `g4d8e1f2a760`.
- Full offline migration SQL generation passed.
- TypeScript/TSX syntax scan: **312 files, zero syntax diagnostics**.
- Local frontend import scan: **zero missing imports**.
- Potential unused-import scan: **zero findings**.
- Native browser `alert`, `confirm` and `prompt`: **zero findings**.
- Business components importing the raw Dialog root: **zero findings**.

A dependency-aware `pnpm typecheck`, ESLint and Next.js production build could not be run in this isolated environment because the archive did not contain `node_modules` and package downloads were unavailable. Run them locally after extraction.

## Local frontend validation

```bash
cd frontend
rm -rf .next
pnpm install
pnpm typecheck
pnpm lint
pnpm build
pnpm dev
```

## No seed or dummy business data

This release does not create sample borrowers, products, applications or loans. Empty states guide authorized users to create real records through editable forms.
