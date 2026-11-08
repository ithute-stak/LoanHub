# Deployment-free integration sequence — review before any GitHub writes

**Current package is offline source; not a drop-in production release.** It is not valid to promise a fully operational payment gateway without the real provider specifications, approved mandates, accounting schema mapping and production security certification.

## Suggested pull-request sequence

1. **PR A — domain contracts:** Move audited pure-domain modules into an *inactive, non-routed* package; preserve existing LoanHub / IthutePay imports and service wiring. Run unit tests.
2. **PR B — database pilot:** Compare the synthetic Phase 42 schema with LoanHub actual `loan_companies`, `client_company_loan`, `borrowers`, repayment, journals and tenant context. Create a separate, approved Alembic migration only after DBA review. Enforce composite FKs, tenant RLS, transaction ownership, restricted grants, immutable audit, uniqueness and policy signatures. Run PostgreSQL 16 concurrency + rollback tests. The provided SQL is **not** that migration.
3. **PR C — provider-boundary certification:** Inspect direct M-PESA production integration (preserve it), integrate each provider's *documented* callback verification, replay storage, timeout and reference mapping. Use sandbox credentials; keep Golink optional. No credential values in code/PRs.
4. **PR D — transactional financial posting:** Only after approved policy and mandate rules, implement row-locked loan balances, per-tenant ledger, outbox and provider event deduplication in one database transaction. Verify atomic rollback and unique posting references on real LoanHub mappings.
5. **PR E — reconciliation & reversals:** Import actual provider statements through least-privilege signed channels, compare to ledger, hold mismatches for independent approval, prove reversal is equal/opposite, test late settlements.
6. **PR F — staging certification:** Deploy to isolated staging only with synthetic borrowers and separate test merchant; run outage, TLS, tenant-isolation, security, backup/restore and release rollback tests. All financial gates remain off outside approved staging.

## Required independent external inputs

- Vodacom Lesotho direct M-PESA documented collection API, callback signing/authentication, merchant terms, production/sandbox test requirements and consent flow.
- Other provider documentation (Econet, Golink) only if selected by a tenant; adapters must not replace the original direct M-PESA implementation.
- Tenant-specific signed lending and fee agreements, debt collection mandate evidence, local law/regulatory review.
- Existing LoanHub and IthutePay migration ancestry, account chart, service routes and company scope at merge time.
- Security and financial signoff from designated human reviewers.

## Production hard stops

- No automatic provider call from a preview or reference module.
- No use of master merchant for other businesses without explicit merchant custody authorization and fee agreement.
- No enabled payments based only on passing offline tests.
- No `ALTER TABLE` from this package applied to production.
- No user identifiers or secrets in logs.
- No assumption that a provider-specific signature is HMAC without its official specification.
- Unknown provider outcome must be reconciled, **never automatically retried as a fresh debit**.
