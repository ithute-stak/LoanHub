fn round_ratio_half_up(numerator: i128, denominator: i128) -> i64 {
    if denominator <= 0 {
        return -1;
    }
    let negative = numerator < 0;
    let absolute = if negative { -numerator } else { numerator };
    let mut quotient = absolute / denominator;
    let remainder = absolute % denominator;
    if remainder.saturating_mul(2) >= denominator {
        quotient = quotient.saturating_add(1);
    }
    let signed = if negative { -quotient } else { quotient };
    if signed > i64::MAX as i128 || signed < i64::MIN as i128 {
        return -1;
    }
    signed as i64
}

/// Browser-only cash-flow preview. Server-side Python remains authoritative.
#[no_mangle]
pub extern "C" fn affordability_headroom_cents(
    income_cents: i64,
    commitments_cents: i64,
    proposed_installment_cents: i64,
) -> i64 {
    income_cents
        .saturating_sub(commitments_cents)
        .saturating_sub(proposed_installment_cents)
}

/// Browser-only simple/flat-interest total preview using integer cents.
///
/// rate_milli_percent: 36.125% => 36125.
/// Returns -1 for invalid inputs.
#[no_mangle]
pub extern "C" fn simple_interest_total_cents(
    principal_cents: i64,
    rate_milli_percent: i64,
    months: i32,
    processing_fee_cents: i64,
) -> i64 {
    if principal_cents <= 0
        || rate_milli_percent < 0
        || months <= 0
        || months > 120
        || processing_fee_cents < 0
    {
        return -1;
    }

    let numerator =
        principal_cents as i128
        * rate_milli_percent as i128
        * months as i128;
    let denominator = 1000_i128 * 100_i128 * 12_i128;
    let interest_cents = round_ratio_half_up(numerator, denominator);
    if interest_cents < 0 {
        return -1;
    }

    principal_cents
        .saturating_add(interest_cents)
        .saturating_add(processing_fee_cents)
}
