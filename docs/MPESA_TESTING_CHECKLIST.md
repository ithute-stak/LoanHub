# M-Pesa sandbox testing checklist

Use the detailed DOCX/PDF testing manual delivered with the release. This file is the quick engineering checklist.

## Installation

- [ ] Back up PostgreSQL.
- [ ] Apply Alembic head `b8d5e21f9a30`.
- [ ] Restart API and maintenance worker.
- [ ] Set `PAYMENT_MOCK_MODE=false` only when using actual M-Pesa sandbox credentials.
- [ ] Configure company sandbox API key, public key, shortcode, origin and enabled products.
- [ ] Test SessionKey from the Company M-Pesa page.

## Borrower

- [ ] Single-stage repayment creates one local payment and one provider attempt.
- [ ] Multi-stage repayment shows processing until final confirmation.
- [ ] Refresh status cannot be spammed faster than the borrower throttle.
- [ ] Duplicate idempotency key returns the original transaction.
- [ ] Successful repayment updates balance and creates a PDF receipt.
- [ ] Direct-debit creation requires explicit consent.
- [ ] New mandate remains pending until Query Direct Debit confirms active.
- [ ] Borrower can cancel own mandate.

## Company

- [ ] Beneficiary name is queried before B2C loan disbursement.
- [ ] Only authorised finance roles can disburse, collect, B2B or request reversals.
- [ ] Branch users see only branch-linked transactions.
- [ ] B2B creates an outbound accounting transaction.
- [ ] Direct-debit collection works only for an active mandate.
- [ ] Reversal requires request and management approval.
- [ ] Original receipt remains after reversal.
- [ ] Multi-stage status update is limited to relevant transactions.

## Platform owner

- [ ] Overview totals match provider transaction records.
- [ ] Company configurations are visible without exposing API/public key values.
- [ ] Platform owner can review user/company queries and respond.
- [ ] Unmatched callbacks are visible for investigation.

## Resilience

- [ ] Simulated timeout leaves transaction `processing`.
- [ ] Provider attempt exists before the network call.
- [ ] Maintenance worker later queries and finalises the transaction.
- [ ] Duplicate callback does not duplicate allocation/accounting/receipt.
- [ ] `INS-9` triggers status enquiry, not a second payment.
- [ ] `INS-13`, `INS-20`, `INS-21`, `INS-28`, `INS-997`, `INS-998` surface safe operator guidance.

## UI

- [ ] Query, Chat and Assistant controls never overlap.
- [ ] Assistant panel opens above the dock on phones.
- [ ] M-Pesa pages are usable at 320px, tablet and desktop widths.
- [ ] Dialog content scrolls while actions remain reachable.
