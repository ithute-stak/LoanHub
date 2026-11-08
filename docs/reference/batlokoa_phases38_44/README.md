# LoanHub ↔ IthutePay — Expanded Complete Offline Engineering Bundle

**Prepared 8 November 2026. Offline source only. No GitHub commits, Actions, provider requests or production deployment.**

This expanded package contains the original Phase 35 reference source, the
Phase 38–41 domain package, and **additional Phase 42 integration scaffolding**.
It represents a comprehensive offline *engineering handoff*, **not** a complete,
certified, operational payment gateway. Provider security specifications,
production database mappings, consent mechanisms and regulatory approvals
cannot be invented or considered completed by offline tests.

## New Phase 42 modules

| File | What it implements |
|---|---|
| `completion_engine/mandates.py` | Time-bounded, amount-bounded, borrower-linked, independently verified mandate contract |
| `completion_engine/provider_registry.py` | Provider safety registry preserving direct M-PESA as an independent rail |
| `completion_engine/callback_intake.py` | Verified callback input and replay classification, no insecure fake live verification |
| `completion_engine/provider_event_store.py` | Transactional provider event deduplication with conflict detection |
| `completion_engine/financial_invariants.py` | Reconciled settlement posting and equal/opposite reversal validation |
| `completion_engine/atomic_repository.py` | Disabled-by-default PostgreSQL journal/event/outbox SQL adapter in one caller-owned transaction |
| `completion_engine/recovery.py` | Safe unknown-outcome and reversal recovery classification |
| `completion_engine/outbox_worker.py` | Safe lease, delivery ACK, retry/backoff and dead-letter model |
| `completion_engine/fee_policy.py` | Contractual platform pricing with **unknown provider charges left unknown** |
| `completion_tests/test_completion.py` | 30 additional integration-boundary unit tests |
| `completion_tests/test_postgres_optional.py` | Three real PostgreSQL test cases (skipped unless disposable DB configured) |
| `schemas/phase42_isolated_postgres.sql` | Synthetic CI fixture only, **not a migration** |
| `guides/REMOTE_INTEGRATION_PLAN.md` | Six-PR implementation and deployment isolation plan |
| `guides/RELEASE_AND_TEST_MATRIX.md` | Explicit remaining real-world certification evidence |
| `ci_templates/phase42-offline-review.yml` | Review-only CI template, not installed in any repo |

## Run offline tests

```bash
cd Batlokoa_Complete_Remaining_Offline_Implementation_2026-11-08
python3 run_all_tests.py
```

Expect **86 passing offline unit tests and three skipped optional PostgreSQL integration tests**. The inherited Phase 35 `future_activation/` prototype tests can be run separately; some require SQLAlchemy/pytest. Offline success cannot certify PostgreSQL RLS, real provider callbacks, live settlement or customer permissions.

## Run optional disposable PostgreSQL tests

Use a dedicated disposable database only, never a shared or production connection.

```bash
python3 -m pip install -r requirements-optional-postgres.txt
export BATLOKOA_OFFLINE_TEST_POSTGRES_URL='postgresql://test_user:password@127.0.0.1:5432/disposable_finance_test'
python3 -m unittest -v completion_tests.test_postgres_optional
```

The tests create their own random schema, then drop it. They do **not** prove complete financial accounting or tenant permissions.

## Safety restrictions

- The default SQL write pathways require explicit `enabled=True` and are not registered into any active LoanHub or IthutePay service.
- No real Vodacom/Econet/Golink adapter implementations or credentials are fabricated. Each provider needs official specifications and sandbox certification.
- Preserve the existing **direct Vodacom M-PESA** integration and shortcode **38542**. Golink must remain optional and replaceable.
- No actual collection, payout, settlement, shared custody, debit or disbursement operation occurs anywhere in this package.
- The historical Phase 35 `apply_code.py` is archived only: **DO NOT RUN IT** against `main` because newer code is already merged.
- Do not install the `.sql` files as production migrations.

## Incomplete external dependencies

Actual company/loan model mapping; signed legal mandates and approved company rules; provider-specific webhook verification, provider agreements and real sandbox credentials; actual financial journal posting and reconciliation; production security and recovery certification. These are operational prerequisites, not files that can responsibly be generated from assumptions.


## Previous bundle overview

# Batlokoa ↔ LoanHub ↔ IthutePay — Offline Remaining Engineering Bundle

**Prepared 8 November 2026. No GitHub writes, CI, migrations or deployments.**

This ZIP includes the earlier **Phase 35 source bundle** under
`Batlokoa_Offline_Financial_Engine_Phase35/` plus new independent **Phase
38–41** offline contracts under `remaining_engine/`. It is **not** an
integrated production payment system; external provider contracts, legal
mandate rules and database mapping remain necessary.

| Phase | Offline source | Scope |
|---|---|---|
| 38 | `transaction_integrity.py`, `audit_outbox.py` | Versioned transitions, verified evidence requirements, hash-chained events and proposed outbox messages |
| 39 | `ledger_posting.py`, `settlement_plan.py` | Approved-policy allocation, balanced journal and full reversal proposals, matched settlement precondition |
| 40 | `provider_boundary.py`, `reconciliation.py` | Provider verification protocol, fail-closed adapter acceptance, settlement exceptions |
| 41 | `certification.py`, guides | Evidence-gated staging release checklist, runbook and provider gaps |

Additional reference SQL in `schemas/` is **NOT AN ALEMBIC MIGRATION**. It
must not be executed on production systems. Financial schemas require actual
LoanHub composite FK mapping, durable RLS/roles, transaction and audit design.

Run the new offline tests (Python standard library only):

```sh
cd Batlokoa_Phases38_41_Offline_2026-11-08
python3 -m unittest discover -s tests -v
```

The inherited Phase 35 bundle includes its own optional SQLAlchemy/pytest
prototype tests and a retired staging installer. Do not run its `apply_code.py`
on an already-integrated LoanHub checkout. Those prior versions were merged
through PRs #610–615, with selective adaptations, not byte-identical imports.

**Do not modify the direct Vodacom M-PESA integration or shortcode 38542.**
Do not enable financial execution or approve provider adapters using only the
synthetic examples here. All deployments, GitHub actions and migrations are
reserved for an explicit later review and approval.


## Phase 43 supplemental code (8 November 2026)

This release includes five new review-only financial operations modules and
36 new unit tests under `phase43_engine/` and `phase43_tests/`. The unified
test runner includes all phases 38–43. See `guides/PHASE43_SCOPE_AND_LIMITS.md`.
**Not a certified production payment system.** No source was pushed to GitHub.


## Phase 44 integrated offline transaction coordinator

Added `phase44/contracts.py`, `phase44/store.py`, `phase44/coordinator.py`, `phase44/audit.py`, and `tests/test_phase44.py`. These provide synthetic end-to-end transaction state, deduplication, provider-event binding, journal/reversal proposals, transactional outbox and audited rollback. See `PHASE44_INTEGRATION_AND_LIMITS.md`. **This is not a real provider adapter or production payment processing.**

Run `python3 run_all_tests.py` to execute all offline Phase 38–44 tests.
