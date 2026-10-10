#include <boost/multiprecision/cpp_int.hpp>
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using boost::multiprecision::cpp_int;

namespace {

constexpr std::int64_t MONTHLY_RATE_DENOMINATOR = 1'200'000;

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

std::int64_t round_big_ratio_half_up(cpp_int numerator, const cpp_int& denominator) {
    if (denominator <= 0) {
        throw std::invalid_argument("denominator must be positive");
    }
    const bool negative = numerator < 0;
    if (negative) {
        numerator = -numerator;
    }
    cpp_int quotient = numerator / denominator;
    const cpp_int remainder = numerator % denominator;
    if (remainder * 2 >= denominator) {
        quotient += 1;
    }
    if (negative) {
        quotient = -quotient;
    }
    const cpp_int maximum = std::numeric_limits<std::int64_t>::max();
    const cpp_int minimum = std::numeric_limits<std::int64_t>::min();
    if (quotient > maximum || quotient < minimum) {
        throw std::overflow_error("big-ratio result exceeds int64");
    }
    return quotient.convert_to<std::int64_t>();
}

cpp_int pow_int(cpp_int base, std::int64_t exponent) {
    cpp_int result = 1;
    while (exponent > 0) {
        if (exponent & 1) {
            result *= base;
        }
        exponent >>= 1;
        if (exponent > 0) {
            base *= base;
        }
    }
    return result;
}

std::vector<std::int64_t> split_cents(std::int64_t total_cents, std::int64_t count) {
    if (count <= 0 || count > 120) {
        throw std::invalid_argument("invalid installment count");
    }
    const std::int64_t regular = round_ratio_half_up(total_cents, count);
    std::vector<std::int64_t> values(static_cast<std::size_t>(count), regular);
    const __int128 prior =
        static_cast<__int128>(regular) * static_cast<__int128>(count - 1);
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

std::int64_t checked_i64(const __int128 value, const char* message) {
    if (
        value > std::numeric_limits<std::int64_t>::max()
        || value < std::numeric_limits<std::int64_t>::min()
    ) {
        throw std::overflow_error(message);
    }
    return static_cast<std::int64_t>(value);
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

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 5 && std::string(argv[1]) == "simple-interest") {
            const std::int64_t principal_cents = parse_i64(argv[2]);
            const std::int64_t rate_milli_percent = parse_i64(argv[3]);
            const std::int64_t months = parse_i64(argv[4]);
            if (
                principal_cents < 0
                || rate_milli_percent < 0
                || months <= 0
                || months > 120
            ) {
                return 2;
            }
            const __int128 numerator =
                static_cast<__int128>(principal_cents)
                * static_cast<__int128>(rate_milli_percent)
                * static_cast<__int128>(months);
            const __int128 denominator =
                static_cast<__int128>(1000) * 100 * 12;
            std::cout << round_ratio_half_up(numerator, denominator) << "\n";
            return 0;
        }

        if (
            argc == 6
            && (
                std::string(argv[1]) == "simple-flat-preview"
                || std::string(argv[1]) == "micro-loan-preview"
                || std::string(argv[1]) == "reducing-balance-preview"
                || std::string(argv[1]) == "compound-interest-preview"
            )
        ) {
            const std::int64_t principal_cents = parse_i64(argv[2]);
            const std::int64_t rate_milli_percent = parse_i64(argv[3]);
            const std::int64_t months = parse_i64(argv[4]);
            const std::int64_t fee_cents = parse_i64(argv[5]);
            const std::string command = argv[1];

            if (command == "simple-flat-preview") {
                simple_flat_preview(
                    principal_cents, rate_milli_percent, months, fee_cents
                );
            } else if (command == "micro-loan-preview") {
                micro_loan_preview(
                    principal_cents, rate_milli_percent, months, fee_cents
                );
            } else if (command == "reducing-balance-preview") {
                reducing_balance_preview(
                    principal_cents, rate_milli_percent, months, fee_cents
                );
            } else {
                compound_interest_preview(
                    principal_cents, rate_milli_percent, months, fee_cents
                );
            }
            return 0;
        }

        std::cerr
            << "usage: loanhub_native simple-interest <principal_cents> <rate_milli_percent> <months>\n"
            << "   or: loanhub_native simple-flat-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n"
            << "   or: loanhub_native micro-loan-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n"
            << "   or: loanhub_native reducing-balance-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n"
            << "   or: loanhub_native compound-interest-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n";
        return 2;
    } catch (...) {
        return 3;
    }
}
