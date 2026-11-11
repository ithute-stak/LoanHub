# LoanHub legacy/new-loan incident — operator reconciliation runbook

**Incident class:** apparent settlement leakage between historical and current loans.
**Default action:** investigate only. Do not bulk reopen completed loans or recompute
balances from national IDs. This document is intentionally free of personal data.

## Verified invariants

- Identity can match across multiple loans: **borrower_id is not loan_id**.
- Legacy-capture linkage is `legacy_loan_captures.loan_id`, not national ID.
- `client_company_loan.status`, `balance` and `amount_paid` are loan-specific.
- `payment_allocations.installment_id` must resolve to the same loan as the
  payment's `loan_id`; company and borrower must match too.
- Completed loans with zero `amount_paid` can be **legitimate top-up parents**.
  Check `loan_top_up_settlements` before proposing repair.
- An early-settled loan may have waived installments; never interpret these as
  receipts without evidence.

## Before examining or repairing production

1. Restrict affected writes and imports using the deployment's approved
   operational controls, with explicit sign-off and a maintenance window.
2. Take a fresh PostgreSQL custom-format backup, checksum it, and verify
   **restoration into an isolated disposable database**. File presence alone
   is not sufficient.
3. Run `scripts/audits/legacy_new_loan_integrity_readonly.sql` with a
   SELECT-only role, limited privileges, `statement_timeout`, and an
   authenticated operator terminal. Do not send row-level identifiers to CI.
4. Compare same-borrower legacy and current **loan IDs and references** with
   original contracts, dated disbursement evidence, actual received payments,
   top-up settlements, early settlements, renewals and reversals.
5. For every suspected loan, separately record:
   - internal loan ID, reference, tenant and borrower ID;
   - source and effective dates of disbursement, repayments, top-ups and adjustments;
   - original terms and approved revised terms;
   - loan-specific payment allocations and any unapplied funds;
   - status/balance as stored in DB versus status/balance in the UI;
   - expected status/balance with supporting evidence and authorized reviewer.
6. Never update `amount_paid` to force a target `balance`; never delete
   historic payments to make a loan look active.
7. If and only if a discrepancy is proved, prepare a **separate repair PR**
   containing an exact allowlist of internal loan IDs, old-value predicates,
   a transactionally captured before-image, accounting journal/reversal
   requirements, dry-run preview, postcondition checks, and rollback procedure.
8. Rehearse against a restored database. Obtain accounting and company-owner
   approval before a controlled production change. Audit every mutation.

## UI isolation checks

- Portfolio: verify a selected row's `loan.id`, `loan_reference`,
  `borrower_id`, `company_id`, status and balance match the detail response.
- History: verify each returned loan's borrower and tenant ownership. Do not
  use the first matching national ID as an active-loan reference.
- Repayment schedule: selected `loan.id` must be used in schedule, receipt and
  repayment endpoints. Compare paid and waived installment statuses separately.
- Top-ups: show completed parent as **settled by top-up** only if backed by
  a verified settlement row; display linked active replacement separately.

## Stop conditions

Stop and escalate rather than changing data when any of the following holds:
- original cash/payment evidence is missing or contradictory;
- multiple financial events could explain the same amount;
- the ledger does not reconcile to bank/merchant evidence;
- the latest backup cannot be restored and validated;
- the repair would cross tenant boundaries, alter an unapproved loan, or
  require an unreviewed correction to accounting entries.

## Findings so far (2026-11-10)

Read-only inspection saw 13 borrowers with both legacy-linked and nonlegacy
loans, including 2 active nonlegacy loans sharing borrower identity with
completed legacy loans. No cross-loan payment-allocation mismatch was
found in that snapshot. Two apparent unpaid completed loans were shown to be
parents in top-up settlements; these are **not proven corruption**.
The reported legacy-to-new settlement leak has **not yet been reproduced**.

No production customer-financial database rows were modified by this incident
investigation.
