use wasm_bindgen::prelude::*;

/// Browser-only preview helper. Server-side Python remains authoritative.
#[wasm_bindgen]
pub fn affordability_headroom_cents(
    income_cents: i64,
    commitments_cents: i64,
    proposed_installment_cents: i64,
) -> i64 {
    income_cents
        .saturating_sub(commitments_cents)
        .saturating_sub(proposed_installment_cents)
}
