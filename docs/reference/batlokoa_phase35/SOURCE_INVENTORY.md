# Offline Phase 35 inventory and staging decision

This repository deliberately separates **merged application code** from
**future-payment reference code**. It must never treat a passing build as
authorization to move funds.

## Current authoritative locations

| Source from offline ZIP | Authoritative repository location | Deployment |
| --- | --- | --- |
| LoanHub preview API router | `apps/backend/routers/batlokoa_collection_preview.py` (PR #610) | Feature-gated; no activation |
| LoanHub preview orchestration | `apps/backend/services/batlokoa_collection_preview_orchestration.py` (PR #610) | Feature-gated; no activation |
| Phase 31 LoanHub tests | `apps/backend/tests/test_batlokoa_collection_preview_*.py` (PR #610) | Tests only |
| Financial allocation | `docs/reference/batlokoa_phase35/financial_allocation.py` (PR #612) | Reference only |
| Journal proposal | `docs/reference/batlokoa_phase35/double_entry.py` (PR #612) | Reference only |
| Payment lifecycle | `docs/reference/batlokoa_phase35/payment_lifecycle.py` (PR #612) | Reference only |
| Provider evidence synthetic verifier | `docs/reference/batlokoa_phase35/provider_evidence.py` (PR #612) | Test-only contract |
| Reconciliation | `docs/reference/batlokoa_phase35/reconciliation.py` (PR #612) | Reference only |
| Idempotency contract | `docs/reference/batlokoa_phase35/idempotency_contract.py` (PR #612) | Reference only |
| PostgreSQL reservation sketch | `docs/reference/batlokoa_phase35/postgres_reservation.py` (PR #612) | NOT installed |
| SQL / RLS drafts | `docs/reference/batlokoa_phase35/*.sql` (PR #612) | NOT migrations |
| Financial/lifecycle tests | `docs/reference/batlokoa_phase35/test_*.py` (PR #612) | Tests only |
| Signed HMAC offline contract | `docs/reference/batlokoa_phase35/wire_contract_reference.py` and `test_wire_contract_reference.py` | Tests only |
| Offline source verification | `docs/reference/batlokoa_phase35/verify_reference.py` | Tests only |
| CI contract execution | `.github/workflows/batlokoa-offline-reference.yml` | CI only |

## Not blindly copied

The offline ZIP's `apply_code.py` is a local staging utility that edits
application source and can be dangerous against the already-merged Phase 31
files. Its job is superseded by the GitHub PR integration and it is not
installed into the running repository. The offline ZIP's repeated copies of
the Phase 31 application files are also not overwritten over the updated
`main` implementations.

Original offline test fixtures and financial sketches were reviewed and
adapted into the repository; identical byte-for-byte reproduction of the ZIP
is **not** claimed. Preserve the ZIP separately for artifact provenance.

## Proof required before actual financial execution

Approved company-specific contracts, mandates, provider-specific callback
security, financial accounting mappings, PostgreSQL RLS/concurrent
idempotency and reconciliation must all pass real integration testing.
Preview outputs are not debit authorizations. The current direct Vodacom
M-PESA integration and shortcode 38542 must remain unchanged.
