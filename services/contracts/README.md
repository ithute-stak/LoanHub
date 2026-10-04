# LoanHub polyglot work-sharing contracts

LoanHub remains authoritative in Python for lending decisions, tenant isolation,
permissions, accounting and provider mutation safety.

Specialized runtimes receive bounded, versioned work:

- Rust: deterministic CPU-heavy calculations and matching.
- Go: concurrent background/network work.
- Java: enterprise event/batch processing and institutional connector work.
- Rust/WASM: non-authoritative browser previews.
- C++: native kernels only behind Rust, after benchmarks justify them.

Every request carries a contract version and correlation id. Workers must never
approve loans, write accounting entries, or mutate Experian/CDAS state directly.
