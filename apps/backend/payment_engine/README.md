# LoanHub payment_engine — isolated foundation

**Status:** policy-preview foundation only. No migrations, no automatic loan
recalculation, and no live posting changes. Existing payment flows remain intact.

## Supported rules (version 1)
- `simple_carry` (default): unpaid part is added to the next scheduled amount.
- `fixed_schedule`: next instalment unchanged; previous arrears shown separately.
- `carry_with_interest`: optional simple charge on **eligible unpaid arrears only**.
  Refuses calculation unless explicitly authorized for the loan and validated
  under applicable law and the signed agreement; no compound interest.

A loan must snapshot its policy at origination. Future policy changes must not
retroactively change signed loans. All three calculations are provisional
previews; production deployment requires jurisdiction-specific compliance
approval and comprehensive multi-period tests.

## Four existing native/runtime languages — integration plan
- **Rust** `services/compute-rust`: deterministic fixed-point financial previews
  with parity vectors against Python's Decimal contract (no float arithmetic).
- **C++** `services/native-cpp`: optional batch numerical acceleration and
  differential checks; never an independent source of debt balances.
- **Go** `services/worker-go`: idempotent event delivery and reconciliation
  digests; no decisions about borrower interest or settlement.
- **Java** `services/worker-java`: versioned policy/event validation and
  auditable rule-evaluation events; no independent ledger mutations.

Python/FastAPI remains the **single authoritative orchestration and database
posting boundary**. Each worker will be introduced behind a feature flag with
deterministic parity tests and fallback. The four language integrations are
planned, **not yet implemented** by this phase.
