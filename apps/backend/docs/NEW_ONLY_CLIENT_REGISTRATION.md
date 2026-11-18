# Phase 68 — New-only registration command boundary (not active)

LoanHub's existing assisted client creation reuses a global borrower on a
national-ID match, potentially updating shared debt, bank, employment and
consent records. This behavior is **not suitable for Batlokoa employee
registration** until historical collisions have been resolved.

The new internal module `services/new_only_client_registration.py` introduces:
- `prepare_new_only_registration_intent`, which accepts an authoritative
  lending-staff tenant context, enforces branch scope and a strict
  idempotency-key shape, and creates a **server-keyed HMAC fingerprint of the
  entire validated request** (including employment, debts and consent).
  The intent never embeds the client's phone or identity number.
- `execute_new_only_registration`, a permanently fail-closed transaction
  outline that uses the Phase 64 identity locking/Phase 63 read-only screening
  and **always refuses a write**. It never calls the old
  `create_assisted_company_client` function and never commits.

This is an architectural boundary, **not a completed registration feature**.
There is no API route or Flutter registration button activated. The current
implementation performs no `User`, `Person`, `Borrower` or
`CompanyBorrowerAccount` insertion.

## Blocking work for an approved write path

- Review Phase 65 audit counts on a disposable reporting database and
  remediate conflicts without changing historical loan outcomes.
- Design/verify database-enforced normalized unique identity constraints and
  coordinate **all** identity writers, not just Batlokoa.
- Add a durable idempotency table with unique company/key constraints,
  replay fingerprint comparison, status lifecycle, and audit linkage.
- Write a fully atomic new-only service that independently inserts new User,
  Person, Borrower and CompanyBorrowerAccount, commits once, and never updates
  another borrower.
- Prove branch attribution, rollback, duplicate submissions, company-specific
  fees, transaction-scoped locks and legacy-loan invariants in isolated
  PostgreSQL staging.
- Security review, staged enablement, and then connect Batlokoa employee UI.

All production registration permissions remain disabled. No historical
repayments, settlements, bank accounts or financial balances are modified.
