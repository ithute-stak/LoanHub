# LoanHub polyglot work sharing

## Authority boundary

Python/FastAPI remains the business authority. No auxiliary runtime may approve
or reject a loan, bypass tenant/role checks, post accounting entries, or perform
untracked Experian/CDAS mutations.

## Runtime responsibilities

| Runtime | Responsibility |
| --- | --- |
| Next.js / TypeScript | UI, workflow state, forms, realtime presentation |
| Rust/WASM | non-authoritative browser previews and heavy client transforms |
| Python | lending policy, affordability authority, accounting, tenancy, orchestration |
| Rust | deterministic high-volume compute and reconciliation kernels |
| Go | concurrent network/background workers and fan-out |
| C++ | benchmark-proven native numerical kernels behind a safer boundary |

## Rollout

Phase 1 adds compile-tested worker boundaries and health/contract surfaces.
Phase 2 moves selected read-only or replayable work behind the workers with
Python fallback. Phase 3 enables workload routing only after parity tests and
benchmarks pass.

CDAS and Experian financial/provider writes remain under the existing Python
safety ledgers. Workers may prepare, hash, parse or reconcile data, but may not
blindly replay provider mutations.
