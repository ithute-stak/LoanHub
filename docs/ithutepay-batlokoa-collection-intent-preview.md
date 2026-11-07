# LoanHub — Batlokoa signed collection-intent preview client

Phase 29 adds an isolated, **disabled-by-default** LoanHub client for
IthutePay's non-posting signed preview API.

`ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED=false` unless separately
approved and configured. It reuses the existing HTTPS origin and dedicated
read-only handshake secret. The working GET handshake is unaffected.

The client prepares opaque references, canonical JSON and signs:

```text
{timestamp}
{nonce}
POST
/api/v1/integrations/loanhub/batlokoa/collection-intent-preview
{company_id}
{sha256_hex_of_exact_body_bytes}
```

The request contains only `amount`, `currency`,
`source_reference` and `idempotency_key`. It does not allow caller-provided
company, application, merchant or shortcode metadata.

Before calling this client, a future LoanHub domain service **MUST**
authenticate its own requester and verify the borrower, loan, tenant,
amount, and reference using LoanHub's authoritative database. This client
does not fetch or validate a borrower's loan ownership on its own and
**must not be exposed directly to the public request layer**.

The response validator requires the exact approved Batlokoa company,
application, merchant, shortcode 38542, inactive app state,
non-enforced zero platform quote, and all of the following set to false:

- `financial_posting_enabled`
- `provider_execution_enabled`
- `idempotency_reserved`
- `provider_charges_included`

This is **not** collection initiation, payment authorization, settlement,
transfer or durable idempotency enforcement. No provider calls or ledger
writes are added to LoanHub. The real payment path stays off until separate
authorization, borrower-ownership checks, durable idempotency constraints,
accounting, fees, settlement and reconciliation are reviewed and tested.

No VPS deployment or feature-flag changes are part of this PR.
