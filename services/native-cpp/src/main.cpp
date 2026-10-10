#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::int64_t parse_i64(const char* raw) {
    return std::stoll(std::string(raw));
}

std::int64_t round_ratio_half_up(__int128 numerator, __int128 denominator) {
    if (denominator <= 0) {
        throw std::invalid_argument("denominator must be positive");
    }
    const bool negative = numerator < 0;
    if (negative) {
        numerator = -numerator;
    }
    __int128 quotient = numerator / denominator;
    const __int128 remainder = numerator % denominator;
    if (remainder * 2 >= denominator) {
        quotient += 1;
    }
    if (negative) {
        quotient = -quotient;
    }
    if (
        quotient > std::numeric_limits<std::int64_t>::max()
        || quotient < std::numeric_limits<std::int64_t>::min()
    ) {
        throw std::overflow_error("result exceeds int64");
    }
    return static_cast<std::int64_t>(quotient);
}

std::vector<std::int64_t> split_cents(std::int64_t total_cents, std::int64_t count) {
    if (count <= 0 || count > 120) {
        throw std::invalid_argument("invalid installment count");
    }
    const std::int64_t regular = round_ratio_half_up(total_cents, count);
    std::vector<std::int64_t> values(static_cast<std::size_t>(count), regular);
    __int128 prior = static_cast<__int128>(regular) * static_cast<__int128>(count - 1);
    const __int128 final_value = static_cast<__int128>(total_cents) - prior;
    if (
        final_value > std::numeric_limits<std::int64_t>::max()
        || final_value < std::numeric_limits<std::int64_t>::min()
    ) {
        throw std::overflow_error("split result exceeds int64");
    }
    values.back() = static_cast<std::int64_t>(final_value);
    return values;
}

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
    const __int128 interest_denominator = static_cast<__int128>(1000) * 100 * 12;
    const std::int64_t interest_cents =
        round_ratio_half_up(interest_numerator, interest_denominator);

    const __int128 total_wide =
        static_cast<__int128>(principal_cents)
        + static_cast<__int128>(interest_cents)
        + static_cast<__int128>(fee_cents);
    if (total_wide > std::numeric_limits<std::int64_t>::max()) {
        throw std::overflow_error("total exceeds int64");
    }
    const std::int64_t total_cents = static_cast<std::int64_t>(total_wide);

    const auto principal_parts = split_cents(principal_cents, months);
    const auto interest_parts = split_cents(interest_cents, months);
    const auto fee_parts = split_cents(fee_cents, months);
    std::vector<std::int64_t> schedule;
    schedule.reserve(static_cast<std::size_t>(months));

    for (std::int64_t i = 0; i < months; ++i) {
        const __int128 row =
            static_cast<__int128>(principal_parts[static_cast<std::size_t>(i)])
            + static_cast<__int128>(interest_parts[static_cast<std::size_t>(i)])
            + static_cast<__int128>(fee_parts[static_cast<std::size_t>(i)]);
        if (row > std::numeric_limits<std::int64_t>::max()) {
            throw std::overflow_error("schedule row exceeds int64");
        }
        schedule.push_back(static_cast<std::int64_t>(row));
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
    const __int128 total_wide = component_sum + static_cast<__int128>(fee_cents);
    const __int128 interest_wide =
        total_wide - static_cast<__int128>(principal_cents) - static_cast<__int128>(fee_cents);
    if (
        total_wide > std::numeric_limits<std::int64_t>::max()
        || interest_wide > std::numeric_limits<std::int64_t>::max()
        || interest_wide < std::numeric_limits<std::int64_t>::min()
    ) {
        throw std::overflow_error("micro-loan result exceeds int64");
    }

    const std::int64_t total_cents = static_cast<std::int64_t>(total_wide);
    const std::int64_t interest_cents = static_cast<std::int64_t>(interest_wide);
    const auto schedule = split_cents(total_cents, months);
    emit_preview(schedule.front(), interest_cents, total_cents, schedule);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        // Backward-compatible exact interest kernel.
        // simple-interest <principal_cents> <rate_milli_percent> <months>
        if (argc == 5 && std::string(argv[1]) == "simple-interest") {
            const std::int64_t principal_cents = parse_i64(argv[2]);
            const std::int64_t rate_milli_percent = parse_i64(argv[3]);
            const std::int64_t months = parse_i64(argv[4]);
            if (principal_cents < 0 || rate_milli_percent < 0 || months <= 0 || months > 120) {
                return 2;
            }
            const __int128 numerator =
                static_cast<__int128>(principal_cents)
                * static_cast<__int128>(rate_milli_percent)
                * static_cast<__int128>(months);
            const __int128 denominator = static_cast<__int128>(1000) * 100 * 12;
            std::cout << round_ratio_half_up(numerator, denominator) << "\n";
            return 0;
        }

        // Full fixed-point loan previews. Output:
        // monthly_cents|interest_cents|total_cents|schedule_cents_csv
        if (
            argc == 6
            && (
                std::string(argv[1]) == "simple-flat-preview"
                || std::string(argv[1]) == "micro-loan-preview"
            )
        ) {
            const std::int64_t principal_cents = parse_i64(argv[2]);
            const std::int64_t rate_milli_percent = parse_i64(argv[3]);
            const std::int64_t months = parse_i64(argv[4]);
            const std::int64_t fee_cents = parse_i64(argv[5]);

            if (std::string(argv[1]) == "simple-flat-preview") {
                simple_flat_preview(principal_cents, rate_milli_percent, months, fee_cents);
            } else {
                micro_loan_preview(principal_cents, rate_milli_percent, months, fee_cents);
            }
            return 0;
        }

        std::cerr
            << "usage: loanhub_native simple-interest <principal_cents> <rate_milli_percent> <months>\n"
            << "   or: loanhub_native simple-flat-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n"
            << "   or: loanhub_native micro-loan-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n";
        return 2;
    } catch (...) {
        return 3;
    }
}
