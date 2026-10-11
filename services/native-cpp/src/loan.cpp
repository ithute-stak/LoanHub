#include "native.hpp"

namespace loanhub_native {

void emit_preview(
    std::int64_t monthly_cents,
    std::int64_t interest_cents,
    std::int64_t total_cents,
    const std::vector<std::int64_t>& schedule
) {
    std::cout << monthly_cents << "|" << interest_cents << "|" << total_cents << "|";
    for (std::size_t i = 0; i < schedule.size(); ++i) {
        if (i > 0) {
            std::cout << ",";
        }
        std::cout << schedule[i];
    }
    std::cout << "\n";
}

void validate_loan_inputs(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents
) {
    if (
        principal_cents <= 0
        || rate_milli_percent < 0
        || months <= 0
        || months > 120
        || fee_cents < 0
    ) {
        throw std::invalid_argument("invalid loan inputs");
    }
}

void simple_flat_preview(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents
) {
    validate_loan_inputs(principal_cents, rate_milli_percent, months, fee_cents);

    const __int128 interest_numerator =
        static_cast<__int128>(principal_cents)
        * static_cast<__int128>(rate_milli_percent)
        * static_cast<__int128>(months);
    const __int128 interest_denominator =
        static_cast<__int128>(1000) * 100 * 12;
    const std::int64_t interest_cents =
        round_ratio_half_up(interest_numerator, interest_denominator);

    const std::int64_t total_cents = checked_i64(
        static_cast<__int128>(principal_cents)
            + static_cast<__int128>(interest_cents)
            + static_cast<__int128>(fee_cents),
        "total exceeds int64"
    );

    const auto principal_parts = split_cents(principal_cents, months);
    const auto interest_parts = split_cents(interest_cents, months);
    const auto fee_parts = split_cents(fee_cents, months);
    std::vector<std::int64_t> schedule;
    schedule.reserve(static_cast<std::size_t>(months));

    for (std::int64_t i = 0; i < months; ++i) {
        schedule.push_back(checked_i64(
            static_cast<__int128>(principal_parts[static_cast<std::size_t>(i)])
                + static_cast<__int128>(interest_parts[static_cast<std::size_t>(i)])
                + static_cast<__int128>(fee_parts[static_cast<std::size_t>(i)]),
            "schedule row exceeds int64"
        ));
    }

    emit_preview(schedule.front(), interest_cents, total_cents, schedule);
}

void micro_loan_preview(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents
) {
    validate_loan_inputs(principal_cents, rate_milli_percent, months, fee_cents);

    const __int128 factor_numerator =
        static_cast<__int128>(100000) + static_cast<__int128>(rate_milli_percent);
    const __int128 factor_denominator = static_cast<__int128>(100000);

    std::int64_t running = principal_cents;
    std::vector<std::int64_t> components;
    components.reserve(static_cast<std::size_t>(months));

    for (std::int64_t month = 0; month < months; ++month) {
        const std::int64_t amount_after_rate = round_ratio_half_up(
            static_cast<__int128>(running) * factor_numerator,
            factor_denominator
        );
        const bool final_month = month + 1 == months;
        const std::int64_t component = final_month
            ? amount_after_rate
            : round_ratio_half_up(amount_after_rate, 2);
        running = final_month ? 0 : amount_after_rate - component;
        components.push_back(component);
    }

    __int128 component_sum = 0;
    for (const auto value : components) {
        component_sum += static_cast<__int128>(value);
    }
    const std::int64_t total_cents = checked_i64(
        component_sum + static_cast<__int128>(fee_cents),
        "micro-loan total exceeds int64"
    );
    const std::int64_t interest_cents = checked_i64(
        static_cast<__int128>(total_cents)
            - static_cast<__int128>(principal_cents)
            - static_cast<__int128>(fee_cents),
        "micro-loan interest exceeds int64"
    );
    const auto schedule = split_cents(total_cents, months);
    emit_preview(schedule.front(), interest_cents, total_cents, schedule);
}

void reducing_balance_preview(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents
) {
    validate_loan_inputs(principal_cents, rate_milli_percent, months, fee_cents);

    std::int64_t base_payment_cents = 0;
    if (rate_milli_percent == 0) {
        base_payment_cents = round_ratio_half_up(principal_cents, months);
    } else {
        const cpp_int rate_numerator = rate_milli_percent;
        const cpp_int rate_denominator = MONTHLY_RATE_DENOMINATOR;
        const cpp_int growth_numerator =
            pow_int(rate_denominator + rate_numerator, months);
        const cpp_int growth_denominator =
            pow_int(rate_denominator, months);
        const cpp_int numerator =
            cpp_int(principal_cents) * rate_numerator * growth_numerator;
        const cpp_int denominator =
            rate_denominator * (growth_numerator - growth_denominator);
        base_payment_cents = round_big_ratio_half_up(numerator, denominator);
    }

    const auto fee_parts = split_cents(fee_cents, months);
    std::int64_t opening = principal_cents;
    __int128 total_interest_wide = 0;
    std::vector<std::int64_t> schedule;
    schedule.reserve(static_cast<std::size_t>(months));

    for (std::int64_t index = 0; index < months; ++index) {
        const std::int64_t interest_due = round_ratio_half_up(
            static_cast<__int128>(opening)
                * static_cast<__int128>(rate_milli_percent),
            MONTHLY_RATE_DENOMINATOR
        );
        std::int64_t principal_due = 0;
        if (index + 1 == months) {
            principal_due = opening;
        } else {
            const std::int64_t candidate =
                std::max<std::int64_t>(0, base_payment_cents - interest_due);
            principal_due = std::min(opening, candidate);
        }
        opening = std::max<std::int64_t>(0, opening - principal_due);
        total_interest_wide += static_cast<__int128>(interest_due);
        schedule.push_back(checked_i64(
            static_cast<__int128>(principal_due)
                + static_cast<__int128>(interest_due)
                + static_cast<__int128>(fee_parts[static_cast<std::size_t>(index)]),
            "reducing-balance schedule row exceeds int64"
        ));
    }

    const std::int64_t total_interest_cents =
        checked_i64(total_interest_wide, "reducing-balance interest exceeds int64");
    __int128 total_wide = 0;
    for (const auto value : schedule) {
        total_wide += static_cast<__int128>(value);
    }
    const std::int64_t total_cents =
        checked_i64(total_wide, "reducing-balance total exceeds int64");
    emit_preview(schedule.front(), total_interest_cents, total_cents, schedule);
}

void compound_interest_preview(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents
) {
    validate_loan_inputs(principal_cents, rate_milli_percent, months, fee_cents);

    std::int64_t notional = principal_cents;
    std::vector<std::int64_t> rounded_interest;
    rounded_interest.reserve(static_cast<std::size_t>(months));
    for (std::int64_t month = 0; month < months; ++month) {
        const std::int64_t interest = round_ratio_half_up(
            static_cast<__int128>(notional)
                * static_cast<__int128>(rate_milli_percent),
            MONTHLY_RATE_DENOMINATOR
        );
        rounded_interest.push_back(interest);
        notional = checked_i64(
            static_cast<__int128>(notional) + static_cast<__int128>(interest),
            "compound notional exceeds int64"
        );
    }

    const cpp_int rate_numerator = rate_milli_percent;
    const cpp_int rate_denominator = MONTHLY_RATE_DENOMINATOR;
    const cpp_int growth_numerator =
        pow_int(rate_denominator + rate_numerator, months);
    const cpp_int growth_denominator =
        pow_int(rate_denominator, months);
    const std::int64_t exact_total_interest_cents = round_big_ratio_half_up(
        cpp_int(principal_cents) * (growth_numerator - growth_denominator),
        growth_denominator
    );

    if (!rounded_interest.empty()) {
        __int128 prior = 0;
        for (std::size_t i = 0; i + 1 < rounded_interest.size(); ++i) {
            prior += static_cast<__int128>(rounded_interest[i]);
        }
        rounded_interest.back() = checked_i64(
            static_cast<__int128>(exact_total_interest_cents) - prior,
            "compound final interest exceeds int64"
        );
    }

    const auto principal_parts = split_cents(principal_cents, months);
    const auto fee_parts = split_cents(fee_cents, months);
    std::vector<std::int64_t> schedule;
    schedule.reserve(static_cast<std::size_t>(months));
    __int128 total_wide = 0;

    for (std::int64_t index = 0; index < months; ++index) {
        const auto i = static_cast<std::size_t>(index);
        const std::int64_t row = checked_i64(
            static_cast<__int128>(principal_parts[i])
                + static_cast<__int128>(rounded_interest[i])
                + static_cast<__int128>(fee_parts[i]),
            "compound schedule row exceeds int64"
        );
        schedule.push_back(row);
        total_wide += static_cast<__int128>(row);
    }

    const std::int64_t total_cents =
        checked_i64(total_wide, "compound total exceeds int64");
    emit_preview(
        schedule.front(),
        exact_total_interest_cents,
        total_cents,
        schedule
    );
}

} // namespace loanhub_native
