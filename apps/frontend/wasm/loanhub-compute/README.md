# LoanHub Rust/WASM preview package

This package is for browser acceleration only. It must never become the source
of truth for approval, affordability, accounting, Experian or CDAS mutations.

Build when wasm-pack is available:

```bash
wasm-pack build --target web
```

The frontend should always submit final lending inputs to the Python API for an
authoritative calculation.
