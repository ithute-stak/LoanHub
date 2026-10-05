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
| Python | final lending authority, provider/database orchestration, accounting, tenancy and audit persistence |
| Rust | deterministic affordability math, loan calculations, portfolio-risk aggregation and reconciliation kernels |
| Go | bounded concurrent network/background work, webhook fan-out and replayable reconciliation hashing |
| Java | deterministic underwriting/business-rule evaluation, enterprise event processing and institutional batch pipelines |
| C++ | benchmark-proven exact integer-cents numerical kernels invoked behind Rust with parity protection |

## Rollout

Phase 1 adds compile-tested worker boundaries and health/contract surfaces.
Phase 2 moves selected read-only or replayable work behind the workers with
Python fallback. Current examples include Go reconciliation hashing, Rust
reconciliation classification and parity-checked loan previews, Java
webhook-event canonicalization, a C++ integer-cents simple-interest kernel
invoked behind Rust, and Rust/WASM browser previews checked against the
authoritative Python API result. Phase 3 expands workload routing only after
parity tests and benchmarks pass.

CDAS and Experian financial/provider writes remain under the existing Python
safety ledgers. Workers may prepare, hash, parse or reconcile data, but may not
blindly replay provider mutations.


## Underwriting work sharing

The quick-loan affordability path now deliberately separates calculation from authority:

1. Python loads the borrower, tenant and lender policy and computes the authoritative reference result.
2. Rust computes the same affordability metrics using deterministic decimal arithmetic.
3. Python performs field-for-field parity verification. A mismatch records runtime telemetry and falls back to Python.
4. Java independently evaluates the lender rule outcomes and standardized reason codes from the calculated metrics.
5. Python parity-checks Java's rule decision/reasons before accepting a prefer-worker result.
6. Python remains the only component allowed to persist or act on the final lending decision.

Shadow remains the default for both new workloads. Controlled promotion to prefer-worker should happen only after the polyglot benchmark history shows 100% parity, 100% worker availability and latency within the configured threshold.

Go is intentionally not inserted into synchronous affordability arithmetic: its production value is concurrent I/O and fan-out, where it already owns bounded webhook delivery and replayable reconciliation hashing. C++ remains behind Rust for exact native integer-cents kernels where a native boundary is benchmark-proven; it is not called merely to increase language count.
