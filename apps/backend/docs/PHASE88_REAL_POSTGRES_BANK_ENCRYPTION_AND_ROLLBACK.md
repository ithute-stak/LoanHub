# Phase 88 — Encrypted bank capture and rollback on actual PostgreSQL

Phase 87 has merged with passing CI. This phase extends the **isolated**
PostgreSQL new-client tests to cover the actual bank-account persistence
path in the full registration transaction.

Test 1 creates a synthetic new borrower, declared external debt and FNB
bank account. It verifies that the SQL bank row retains the expected bank,
last-four digits, salary-account selection and `unverified` status; that
neither the plaintext account number nor provider token is present in the
stored ciphertext fields; and that replaying the identical idempotency
key creates no duplicate bank rows.

Test 2 injects a failure after the bank row and external debt have been
staged but before finalization. It verifies the entire borrower, account,
registration, audit, bank and external-debt transaction is rolled back. A
subsequent retry with the same logical idempotency key must create exactly
one bank account and debt obligation.

Both tests operate exclusively on synthetic data in a disposable
`*_sandbox` PostgreSQL database with no production access.

This is evidence of encryption-backed storage and transaction behavior,
**not** a certification of the encryption key lifecycle, bank ownership,
KYC or cash payout authorization. New client registration remains disabled
to live Batlokoa employees pending full governance approvals.
