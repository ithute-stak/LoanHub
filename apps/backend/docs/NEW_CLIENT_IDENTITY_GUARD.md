# Phase 63 — New-client identity guard (no write activation)

This module adds a normalized, read-only screening policy for a future
**new-identity-only** registration flow. It checks:

- Existing persons by normalized national ID or passport number.
- Existing users by normalized phone number or email.
- Batlokoa/tenant-scoped legacy captures by normalized national ID.

It does not reuse, merge, or modify an existing person, borrower, profile,
bank account, loan, loan settlement or legacy capture.

All results have `candidate=false`. A zero-match screening result is
`candidate_requires_transactional_reservation`, **not** permission to write.
This is deliberate: checking then writing without an atomic constraint is
vulnerable to concurrent registration and the existing assisted-create path
can also create identities. Existing exact-value uniqueness constraints do
not fully enforce the normalized matching semantics.

## Remaining production prerequisites

1. Review and remediate duplicate normalized identity collisions before
   introducing any new unique indexes or migrations.
2. Add transaction-safe, database-enforced uniqueness on normalized identity
   attributes, or another rigorously verified reservation mechanism that
   covers all code paths that create borrower identities.
3. Implement idempotency, document-backed identity verification, separate
   new-client vs existing-client-link decisions, and audit evidence.
4. Use dedicated new-only registration endpoint that never falls back to
   reusing an existing global borrower.
5. Prove concurrent registration, rollback, branch authorization and legacy
   settlement invariants against a realistic isolated Postgres staging DB.
6. Only then integrate Batlokoa's employee registration submit action.

No production configuration, data modification or endpoint activation.
