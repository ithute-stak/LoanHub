# Future-only lifecycle engineering review

The state reducer in this folder is deterministic and has no I/O. It does not
grant payment authority, place provider requests or change accounting balances.

**Before integration into a financial API**, independently verify:
- Approved borrower mandate, scope, amount, expiry and revocation
- Company and loan ownership and appropriate role privileges
- Durable idempotency reservations with transactionally enforced uniqueness
- Status compare-and-swap and row locks under concurrent requests
- Verified provider-specific callbacks with replay protections
- Outbox and immutable audit history for event delivery and state mutations
- Reconciliation for UNKNOWN, partial, disputed or late settlements
- Segregated independent reversal approval and accounting reversal
- Verified and separately approved merchant/provider fee agreements

A preview response and its hash are NEVER authority to charge funds.
Existing M-PESA direct integration and shortcode 38542 must be preserved.
