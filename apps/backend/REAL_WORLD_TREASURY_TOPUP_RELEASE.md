# LoanHub Real-World Treasury and Loan Top-Up Release

## Release summary

This release strengthens LoanHub for daily micro-lending operations across headquarters and branches. It introduces an auditable branch treasury cycle, multiple evidence-based payment channels, configurable expense approvals, opening-balance sources, headquarters funding, immutable daily submissions, date-range statements, and controlled loan top-ups.

The migration head for this release is:

```text
k3f1a6b8c240
```

## 1. Daily branch treasury cycle

Each active branch has one financial ledger for each business date.

- **00:01** — LoanHub automatically opens the new financial day in the company’s configured timezone.
- **16:30** — LoanHub automatically submits every still-open branch ledger to the configured headquarters branch.
- Submitted ledgers are locked to protect historical totals.
- An authorised manager can reopen a submitted date with a mandatory reason.
- A reopened current-day ledger is not immediately re-locked by the scheduler after 16:30. Staff can enter the legitimate correction and manually resubmit it. If it remains open, the old-day sweep closes it after the next business date begins.
- Every submission creates a numbered, immutable snapshot. Reopening and resubmitting creates another snapshot rather than silently replacing history.

The schedule is company-configurable, but the default and recommended values are `00:01` and `16:30`.

## 2. Headquarters structure

One active branch is identified as **Headquarters**. Headquarters receives daily activity submissions from all branches and can issue morning funds to individual branches.

A headquarters funding transfer has two controlled sides:

1. Headquarters records money out.
2. The destination branch receives a pending opening source.
3. The destination branch confirms receipt.
4. Only confirmed funding enters that branch’s opening balance.

This avoids counting money at a branch before the branch acknowledges receipt.

## 3. Opening balance architecture

A branch opening balance is not a single manually typed number. It is the sum of confirmed opening sources:

```text
Opening balance
= previous business-day closing balance
+ owner contributions
+ confirmed headquarters funding
+ bank float
+ cash float
+ retained funds
+ authorised opening adjustments
+ other described opening sources
```

The previous closing balance is system-generated and cannot be voided. Other sources retain their description, payment channel, reference, proof and audit information.

The company dashboard consolidates all branch opening sources and displays:

- Previous closing balances
- Owner contributions
- Headquarters funding
- Other opening sources
- Total money in
- Total money out
- Expected closing balance
- Pending expenses

Branch-restricted users receive only their own branch totals; management roles can see the full company position.

## 4. Payment channels

The recognised platform-wide payment methods are:

- Bank
- **Swipped**
- goLink
- CDAS
- M-Pesa Wallet
- M-Pesa Merchant
- M-Pesa Agent
- EcoCash Wallet
- EcoCash Agent
- EcoCash Merchant
- Cash

These values identify how money moved. They do not pretend that a live provider integration occurred. For non-cash channels, staff can capture a transaction/proof reference, proof document location and verification notes.

The legacy misspelling `swiiped` is migrated to `swipped` while preserving historical records.

## 5. Money in and money out

The treasury register supports:

### Money in

- Loan repayments
- Owner contributions
- Other income
- Opening adjustments
- Confirmed branch funding
- Manually verified payment evidence

### Money out

- Loan disbursements
- Operating expenses
- Headquarters branch funding
- Refunds
- Other authorised outflows

Loan disbursements and repayments are posted into the same treasury view, preventing a separate expense register from drifting away from actual lending activity.

## 6. Expense management controls

Expenses capture:

- Branch
- Date and time
- Expense category
- Amount and currency
- Payment channel
- Voucher number
- Description
- Proof/reference
- Supporting document location
- Recording user
- Approval and rejection history

Company owners and administrators maintain reusable expense categories such as Airtime and communication, Transport, Office supplies and Utilities.

### Approval threshold

A company can configure an expense approval threshold. An expense at or above the threshold is saved as **Pending** and does not affect the financial balance until approved.

### Dual control

When dual control is enabled, the person who records a qualifying expense cannot approve it. This creates a maker-checker process suitable for real operations.

### Idempotency

Manual money movements accept an idempotency key. Repeated clicks or retries do not create duplicate expenses.

## 7. Daily submission and transparency

A daily branch submission records:

- Headquarters destination
- Submission sequence
- Automatic or manual submission
- Opening balance
- Total money in
- Total money out
- Expected and declared closing balances
- Variance
- Entry count
- Pending-entry count
- Payment-channel totals
- Expense-category totals
- Opening-source totals
- Submission notes and user

The owner can review every branch, every submission version and every variance.

## 8. Statements and exports

The Money & Expenses workspace supports:

- Date-from and date-to filters
- Branch filter
- Money-in and money-out filter
- Multi-select payment-channel checkboxes
- Selected-channel net total
- Printable statement
- CSV export

Statements exclude voided, rejected and still-pending entries from posted financial totals.

## 9. Loan top-ups

An existing active loan no longer automatically prevents all further lending. The borrower can apply for a controlled **top-up** against the selected existing company loan.

LoanHub uses a replacement-facility model:

```text
New top-up facility
= current outstanding balance of old loan
+ additional cash requested by borrower
```

At disbursement:

- The old balance is settled internally.
- The old loan is completed.
- Only the additional cash portion is recorded as money out to the borrower.
- A top-up settlement audit record links the old and new loans.
- The contract shows both the internal settlement and actual cash paid to the borrower.

This prevents LoanHub from incorrectly treating the entire replacement facility as new cash leaving the company.

## 10. Configurable top-up policy

Each company can configure:

- Allow or disable top-ups
- Minimum percentage of the current loan that must be paid
- Minimum number of paid instalments
- Require positive/non-defaulted payment history
- Enable or disable company-owner exceptions
- Require the replacement facility to settle the old balance

The default paid-percentage threshold is **75%**.

### Owner exception

When the borrower has not reached the normal threshold, the application can request an exceptional top-up only when owner exceptions are enabled. The request requires a reason and can be approved only by the active **Company Owner** role. The original eligibility result and owner decision remain in the audit history.

An unrelated active loan or another open application is still blocked according to the company’s duplicate and concurrent-loan policy.

## 11. Top-up user flow

```text
Company client
→ Credit origination
→ New application
→ Top-up existing loan
→ Select/confirm active loan
→ Enter extra cash requested
→ Automatic replacement-facility calculation
→ KYC and affordability assessment
→ Normal threshold or owner exception
→ Manager approval
→ Contract generation and signatures
→ Finance disbursement
→ Old balance settled + extra cash paid
```

## 12. Main routes

Frontend:

```text
/company/expense-management
/company/origination
/company/origination/new
/company/direct-lending
/company/contracts
/company/loans
/company/cashier
```

Important APIs:

```text
GET    /api/v1/expense-management/dashboard
POST   /api/v1/expense-management/opening-sources
POST   /api/v1/expense-management/entries
POST   /api/v1/expense-management/entries/{id}/approve
POST   /api/v1/expense-management/entries/{id}/reject
POST   /api/v1/expense-management/days/{id}/submit
POST   /api/v1/expense-management/days/{id}/reopen
POST   /api/v1/expense-management/transfers
POST   /api/v1/expense-management/transfers/{id}/receive
GET    /api/v1/expense-management/statements
GET    /api/v1/expense-management/statements/export.csv
POST   /api/v1/expense-management/run-daily-cycle
GET    /api/v1/origination/borrowers/{id}/top-up-eligibility
POST   /api/v1/origination/applications
POST   /api/v1/origination/applications/{id}/top-up-exception/approve
```

## 13. Roles

Recommended operating responsibilities:

- **Company Owner** — policy, top-up exceptions, all-branch oversight, reopen and approval.
- **Company Administrator** — treasury configuration, categories, all-branch operations and reporting.
- **Branch Manager** — branch expenses, approvals, submissions and authorised reopening.
- **Finance Officer** — daily entries, proofs, repayments, disbursements and branch funding operations.
- **Loan Officer** — credit application and top-up preparation.
- **Risk Manager** — affordability and risk review.
- **Auditor** — read-only statements, submissions and audit trails.

Collections officers are not granted general operating-expense write access by this release.

## 14. Installation

Back up PostgreSQL, then run:

```bash
cd apps/backend
alembic current
alembic upgrade head
alembic current
```

Expected head:

```text
k3f1a6b8c240
```

Restart FastAPI so the treasury scheduler starts:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd apps/frontend
rm -rf .next
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm build
pnpm dev
```

## 15. Validation completed

- Backend Python compilation passed.
- SQLAlchemy mapper configuration passed.
- Backend automated tests: **37 passed**.
- SQLAlchemy tables: **71**.
- FastAPI routes: **255**.
- Alembic heads: **1**.
- Full offline upgrade SQL: **4,398 lines**.
- Release downgrade SQL: **124 lines**.
- TypeScript/TSX files parsed: **323**.
- TypeScript syntax diagnostics: **0**.
- Missing local `@/` imports: **0**.
- Active frontend/backend spelling uses `Swipped` / `swipped`.

A dependency-aware Next.js production build was not run in the isolated build environment because the uploaded frontend did not include `node_modules`. Run the listed `pnpm typecheck`, `pnpm lint` and `pnpm build` commands locally before production deployment.

## 16. Security and deployment

The release archives exclude `.env` files, virtual environments, `node_modules`, Next.js build output and JWT private/public key files. Generate deployment secrets on the target environment rather than copying development keys.
