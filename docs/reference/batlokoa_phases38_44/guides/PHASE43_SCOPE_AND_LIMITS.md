# Phase 43 — Additional offline financial controls

This package extends phases 35–42 without touching GitHub or running CI.

## Added
- `phase43_engine/operation_guard.py`: typed tenant/loan/borrower/mandate validation and fail-closed activation gate.
- `phase43_engine/provider_evidence_binding.py`: strict matching of a **previously provider-verified** event to a company, operation, amount and selected rail. **It is not a live provider signature verifier.**
- `phase43_engine/dispute_recovery.py`: versioned dispute state reducer, supporting independent reversal approval and evidence requirements.
- `phase43_engine/statement_matching.py`: read-only per-company/per-provider settlement matching with duplicate and mismatch classification.
- `phase43_engine/release_manifest.py`: checks pinned release artifact hashes and required signoff references. **References alone are not proof of actual authorization.**
- `phase43_tests/test_phase43.py`: executable unit tests (no third-party dependencies).

## Not completed offline
Provider-specific verification must use written Vodacom/Econet/other protocols and actual integration evidence. End-to-end posting must be mapped to LoanHub financial models, real PostgreSQL RLS/foreign keys, mandates and double-entry ledger. Independent reconciliation, stress/load, disaster recovery and regulatory signoffs remain outstanding.

All new functions are library-only and not registered to any LoanHub/IthutePay routes or workers. **Do not enable production charges or replace existing direct Vodacom M-PESA.** Golink is an optional adapter only.
