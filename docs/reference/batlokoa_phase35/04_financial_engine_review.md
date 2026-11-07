# Phase 35 financial domain prototype — review required

All Python files in this directory are **offline reference code**. These
modules have no production imports and are not registered into either
LoanHub or IthutePay payment execution. CI passing does not grant approval.

- **financial_allocation.py:** pure configurable order for charges, interest
  and principal. Real lending companies require legally approved allocation
  rules, Duplum constraints where applicable, accrued interest cutoffs, rounding,
  refund handling and finalized historical balances.
- **double_entry.py:** balanced proposals only. Account mapping, posting dates,
  ledger consistency, transaction locking and immutable audit must be verified.
- **provider_evidence.py:** synthetic HMAC only; NEVER a live Vodacom, Econet,
  Golink or card-payment callback verifier.
- **reconciliation.py:** read-only matching only. No automated ledger posting
  or settlement. Provider and bank statements need certified reconciliation.
- **postgres_reservation.py and SQL:** unapproved RLS and schema sketches.
  Real schema changes need migrations, least-privilege DB roles, company scope,
  concurrency tests, rollback and financial approvals.

These references cannot settle money, reconcile cash automatically, or
legally prove payment mandates. Do not switch on preview or payment flags
through this PR. Preserve all existing providers, including direct M-PESA.
