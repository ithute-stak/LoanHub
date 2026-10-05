# LoanHub Polyglot Service Migration

Python remains the backend authority for tenant scope, permissions, business policy,
accounting, provider write safety, persistence and audit. Specialized runtimes own
bounded work that they are materially better at.

## Runtime ownership

| Runtime | Owns | Does not own |
| --- | --- | --- |
| Python | orchestration, SQLAlchemy persistence, permissions, lending/accounting decisions, Experian/CDAS write safety | CPU-heavy batch loops when a safe delegated implementation exists |
| Rust | deterministic finance, portfolio/risk aggregation, reconciliation, parsing and CPU-heavy analytics | final loan approval or policy |
| C++ | benchmark-proven integer/numerical kernels behind Rust | standalone services or business rules |
| Go | high-concurrency fan-out, network workers, replayable queues and bulk I/O | financial authority or provider mutation policy |
| Java | enterprise event streams, durable batch processing, institutional integration pipelines | loan/accounting authority |
| Rust/WASM | browser-side previews and local compute | authoritative decisions |

## Migration candidates

### Rust
- `interest_calculation_service`: deterministic schedule methods (already delegated).
- `reconciliation_service`: classification plus future batch matching/parsing.
- `portfolio_risk_service`: PAR, grouped risk, concentration, vintages, transition matrices and projected aggregates.
- `analytics_service`: large breakdown/series aggregation after Python applies tenant filters.
- `predictive_intelligence_service`: deterministic score and forecast kernels under parity.
- `credit_loss_provisioning_service`: deterministic scenario/math kernels.
- `early_settlement_service`: deterministic quote math under Python policy control.

### Go
- `mobile_push_service`: multicast/fan-out delivery after Python resolves recipients and payload.
- `webhook_outbox_service`: concurrent delivery attempts for already-authorized, Python-signed outbox rows. Python keeps retry/persistence authority.
- read-only provider polling and bulk network fetches with quota controls.
- file/object-storage transfer workers and other high-concurrency I/O.

### Java
- scheduled report/export batches.
- event enrichment/canonicalisation and durable downstream event processing.
- institutional/enterprise connectors where JVM SDKs or batch semantics are advantageous.
- large scheduled portfolio/report jobs after Python establishes tenant scope.

### C++
- amortisation/vector kernels only when profiling shows measurable gain over Rust.
- large numerical loops used by Rust risk/scenario engines.
- never exposed directly to HTTP or allowed to persist business state.

## Non-migration authority

These stay Python-authoritative even when another runtime computes supporting evidence:
loan approval/rejection, affordability outcome, own-risk override, accounting postings,
disbursement authorization, tenant/role permissions, audit records, Experian policy,
CDAS mutation safety, and final persistence.

## Rollout

Every migrated workload progresses through `off -> shadow -> prefer-worker` where shadow is safe. Side-effecting delivery workloads are an exception: `shadow` remains Python-only so LoanHub never sends duplicate external requests merely to compare runtimes. Promotion requires parity or contract tests, bounded latency, circuit-breaker fallback, and benchmark/history evidence. Cross-process calls should be coarse/batched; do not replace cheap local Python arithmetic with one HTTP request per row.


## Portfolio risk migration status

The Rust portfolio batch now covers PAR thresholds, grouped branch/product/employer
risk, concentration/HHI, delinquency buckets, vintages, top-up performance, top-up
exposure and CDAS exposure in one cross-process request.

- `off`: Python computes the portfolio analytics.
- `shadow`: Python and Rust both compute the same batch and LoanHub records exact
  parity/mismatch evidence.
- `prefer-worker`: Rust computes the migrated aggregate first. Python keeps tenant
  scope and persistence authority and performs the heavy Python calculation only if
  the Rust worker is unavailable or its response is invalid.

This distinction is intentional: continuing to recompute the entire Python aggregate
after promotion would preserve correctness evidence but would not deliver the intended
CPU-efficiency gain.


## Predictive intelligence migration status

Loan-level transparent predictive scoring now has a batched Rust path.

Python continues to own:
- company/branch scope and snapshot selection;
- collection work-item selection;
- evidence construction and advisory-only policy;
- database persistence and auditability;
- all actual credit and collection decisions.

Rust owns the deterministic scoring inner loop: DPD scoring, deterioration,
bucket-worsening, first-payment-default/top-up stress, collection-priority scoring,
risk-band classification, projected PAR30 entry and 30-day stress bucket.

The workload starts in `shadow`. After benchmark/parity evidence supports promotion,
`prefer-worker` uses valid Rust rows directly and falls back to Python only for
missing or invalid worker output. This is the intended efficiency model: once promoted,
LoanHub should not keep paying for the same CPU-heavy Python calculation solely for
live parity on every request.
