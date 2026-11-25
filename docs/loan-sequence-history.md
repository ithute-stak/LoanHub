# Loan Sequence History

Extend the existing repayment schedule activity panel, without changing posting, settlement, or repayment calculation behavior.

## Evidence contract
- Preserve existing activity endpoint authorization and acknowledgement actions.
- Scope records by company, loan, branch and entity identity before pagination; deterministic ordering by timestamp and ID.
- Expose only explicitly allowlisted scalar field changes from recorded before_data and after_data. Never return raw snapshots or arbitrary event metadata.
- Distinguish missing values from explicit null, zero and unchanged values. Do not infer historical values from current borrower or loan records.
- Expose financial before/after and delta only where authoritative, comparable balance evidence exists for the same event and balance definition. Otherwise indicate not recorded. Do not treat contractual scheduled total, principal, cash receipts, waived instalments or settlement discounts as interchangeable.
- Separate recorded cash receipts, allocations, waivers, corrections, reversals and accounting balance movements. Link source records only after authorization.
- A failed or attempted event must not be presented as a successful financial movement.
- Actor identity and role must be sourced from recorded evidence; absent actor is unknown, not automatically system.
- Historical borrower identity, employment, folio, bank account and contacts must be scoped and masked according to permissions. Never overwrite historical snapshots with current profile.
- Loan borrowing order must be based on verified successful issuance, independent of payment and event sequence. Establish explicit top-up and reversal rules before assigning sequence numbers.
- Label incomplete legacy history and paginate without silent truncation.

## Acceptance
Test tenant/branch isolation, secret redaction, absent vs null vs zero, exact decimal arithmetic, nonfinancial events, failed events, partial payments, reversals, settlement discounts, duplicate events, stable pagination, missing historical evidence and preserved acknowledgement. Frontend must support responsive red-dominant LoanHub styling and existing modal conventions.

No production activation or historical mutation is included in this design.
