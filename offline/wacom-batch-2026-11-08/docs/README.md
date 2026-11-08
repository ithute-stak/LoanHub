# LoanHub Wacom — Expanded offline engineering bundle

This package is an **additive source bundle** targeting `ithute-stak/LoanHub` after merged PR #631 and the verified current baseline. It supersedes the earlier small security ZIP.

It does NOT overwrite existing LoanHub payment flows, authentication, tenant code, STU-540 native SDK implementation, or production deployment. It contains domain code, API code, SQL migration, Go client code, a fail-closed opt-in deployment plan, tests and an offline patcher.

## Apply on a clean checkout only

```bash
python3 apply_offline.py --repo /path/to/LoanHub             # dry-run; lists diff
python3 apply_offline.py --repo /path/to/LoanHub --apply     # local files only
cd /path/to/LoanHub
python3 -m compileall -q apps/backend
cd apps/backend && pytest -q tests/test_wacom_document_policy.py
cd ../../services/wacom-connector && go test ./...
```

No branch, PR, push, database migration, customer signature, company user, or deployment occurs automatically. Review diff and run the complete repository quality gate before merging.

## Included source changes

- `wacom_document_policy.py`: immutable tenant/borrower/contract/document/operator/workstation binding; explicit consent commitment; strict state transitions.
- `wacom_document_intent.py`: SQLAlchemy evidence intent records including source PDF hash, consent, attached quarantined capture and independent reviewer.
- `d3e4f5a6b845_...py`: additive Alembic migration, chained after Wacom session migration `c2d3e4f5g834`; review current migration heads before applying.
- `wacom_document_intents.py`: prepare, consent, attach evidence, review, status. Review does **not** generate a signed contract or allow image reuse.
- `loanhub_document_intents.go`: Go HTTPS client for document-specific workflow, validating non-signing server responses.
- `wacom_local_authority.go`: fail-closed local PC permission check.
- `wacom_offline_flow_test.go`: Go safety regression tests.
- `apply_offline.py`: guarded, additive application to existing checkout; proof revocation race and active-account checks; optional strict local-PC mode.
- `tests/test_wacom_document_policy.py`: independently executed domain policy tests.
- `tools/`, `docs/`, `sql/`: verification, staging negative test plan and acceptance evidence templates.

## Critical staged switches

- `LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION=1`: Existing local signature endpoints require current backend device session. Currently opt-in; **staging only** until validated.
- `LOANHUB_WACOM_PC_STRICT=1`: The Go client refuses existing local signature routes without a securely configured private PC identity directory. Requires `--workstation-key-dir`.
- `LOANHUB_WACOM_DOCUMENT_INTENTS_ENABLED=1`: Enables new API for document-specific evidence intents. Requires migration, strict session gate, verified contract ownership schema, and dedicated staging tests. **Keep off by default.**

## What's deliberately NOT represented as finished

1. No genuine physical STU-540 test can be run from an offline ZIP. Existing official SDK capture is reused; the bundle includes a patch connecting Go document methods to the existing localhost UI and SDK capture callback, but this patch has **not been applied or end-to-end validated** in a real LoanHub checkout.
2. The new API records consent/evidence and independent verification, but intentionally does **not** insert handwriting into a PDF, create a legally executed contract, authorize borrowing, or disburse money.
3. The document workflow now uses the existing LoanContract model and verifies its borrower, company, PDF file reference, version and unlocked/unsigned state before consent. Full staging tests are still required.
4. No real end-to-end staging evidence is generated offline. Test the captured image, identity, separate borrower consent and full audit trail on a disposable loan and tenant.
5. Manual verification of regulatory and legal digital signing requirements is required before live contracts.

This is a large engineering batch, not a claim that unvalidated hardware, live external integration, and legal consent are already finished.
