#include <boost/multiprecision/cpp_int.hpp>
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <tuple>
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


struct CivilDate {
    int year;
    unsigned month;
    unsigned day;
};

CivilDate parse_date(const std::string& value) {
    if (value.size() != 10 || value[4] != '-' || value[7] != '-') {
        throw std::invalid_argument("invalid date");
    }
    CivilDate result{
        std::stoi(value.substr(0, 4)),
        static_cast<unsigned>(std::stoul(value.substr(5, 2))),
        static_cast<unsigned>(std::stoul(value.substr(8, 2))),
    };
    if (result.month < 1 || result.month > 12 || result.day < 1 || result.day > 31) {
        throw std::invalid_argument("invalid date");
    }
    return result;
}

bool leap_year(int year) {
    return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
}

unsigned days_in_month(int year, unsigned month) {
    static const unsigned days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (month == 2 && leap_year(year)) {
        return 29;
    }
    return days[month - 1];
}

void validate_date(const CivilDate& value) {
    if (
        value.month < 1
        || value.month > 12
        || value.day < 1
        || value.day > days_in_month(value.year, value.month)
    ) {
        throw std::invalid_argument("invalid calendar date");
    }
}

std::int64_t serial_day(const CivilDate& date) {
    int year = date.year;
    const unsigned month = date.month;
    const unsigned day = date.day;
    year -= month <= 2;
    const int era = (year >= 0 ? year : year - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(year - era * 400);
    const unsigned adjusted_month =
        month > 2 ? month - 3 : month + 9;
    const unsigned doy =
        (153 * adjusted_month + 2) / 5 + day - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return static_cast<std::int64_t>(era) * 146097 + static_cast<std::int64_t>(doe);
}

CivilDate next_day(CivilDate value) {
    const unsigned dim = days_in_month(value.year, value.month);
    if (value.day < dim) {
        ++value.day;
        return value;
    }
    value.day = 1;
    if (value.month < 12) {
        ++value.month;
    } else {
        value.month = 1;
        ++value.year;
    }
    return value;
}

CivilDate month_end(const CivilDate& value) {
    return CivilDate{value.year, value.month, days_in_month(value.year, value.month)};
}

bool date_less_equal(const CivilDate& left, const CivilDate& right) {
    return std::tie(left.year, left.month, left.day)
        <= std::tie(right.year, right.month, right.day);
}

CivilDate min_date(const CivilDate& left, const CivilDate& right) {
    return date_less_equal(left, right) ? left : right;
}

struct BigRatio {
    cpp_int numerator;
    cpp_int denominator;
};

cpp_int big_abs(cpp_int value) {
    return value < 0 ? -value : value;
}

cpp_int big_gcd(cpp_int left, cpp_int right) {
    left = big_abs(std::move(left));
    right = big_abs(std::move(right));
    while (right != 0) {
        cpp_int remainder = left % right;
        left = std::move(right);
        right = std::move(remainder);
    }
    return left == 0 ? cpp_int(1) : left;
}

BigRatio normalize_ratio(cpp_int numerator, cpp_int denominator) {
    if (denominator <= 0) {
        throw std::invalid_argument("invalid ratio denominator");
    }
    const cpp_int divisor = big_gcd(numerator, denominator);
    return BigRatio{numerator / divisor, denominator / divisor};
}

BigRatio add_ratio(const BigRatio& left, const BigRatio& right) {
    return normalize_ratio(
        left.numerator * right.denominator + right.numerator * left.denominator,
        left.denominator * right.denominator
    );
}

BigRatio multiply_ratio(const BigRatio& left, const BigRatio& right) {
    return normalize_ratio(
        left.numerator * right.numerator,
        left.denominator * right.denominator
    );
}

BigRatio reciprocal_ratio(const BigRatio& value) {
    if (value.numerator <= 0) {
        throw std::invalid_argument("cannot invert non-positive ratio");
    }
    return normalize_ratio(value.denominator, value.numerator);
}

BigRatio daily_period_factor_ratio(
    std::int64_t rate_milli_percent,
    CivilDate start_date,
    const CivilDate& end_date
) {
    if (rate_milli_percent == 0 || !date_less_equal(next_day(start_date), end_date)) {
        return normalize_ratio(0, 1);
    }

    BigRatio factor = normalize_ratio(0, 1);
    CivilDate current = next_day(start_date);
    while (date_less_equal(current, end_date)) {
        const CivilDate segment_end = min_date(month_end(current), end_date);
        const std::int64_t days =
            serial_day(segment_end) - serial_day(current) + 1;
        const BigRatio segment = normalize_ratio(
            cpp_int(rate_milli_percent) * days,
            cpp_int(MONTHLY_RATE_DENOMINATOR) * days_in_month(current.year, current.month)
        );
        factor = add_ratio(factor, segment);
        current = next_day(segment_end);
    }
    return factor;
}

std::int64_t daily_segment_interest_cents(
    std::int64_t balance_cents,
    std::int64_t rate_milli_percent,
    CivilDate start_date,
    const CivilDate& end_date
) {
    if (rate_milli_percent == 0 || !date_less_equal(next_day(start_date), end_date)) {
        return 0;
    }

    __int128 total = 0;
    CivilDate current = next_day(start_date);
    while (date_less_equal(current, end_date)) {
        const CivilDate segment_end = min_date(month_end(current), end_date);
        const std::int64_t days =
            serial_day(segment_end) - serial_day(current) + 1;
        total += round_ratio_half_up(
            static_cast<__int128>(balance_cents)
                * static_cast<__int128>(rate_milli_percent)
                * static_cast<__int128>(days),
            static_cast<__int128>(MONTHLY_RATE_DENOMINATOR)
                * static_cast<__int128>(days_in_month(current.year, current.month))
        );
        current = next_day(segment_end);
    }
    return checked_i64(total, "daily interest exceeds int64");
}

std::vector<CivilDate> parse_due_dates(const std::string& csv) {
    std::vector<CivilDate> dates;
    std::size_t start = 0;
    while (start <= csv.size()) {
        const std::size_t comma = csv.find(',', start);
        const std::string token = csv.substr(
            start,
            comma == std::string::npos ? std::string::npos : comma - start
        );
        if (!token.empty()) {
            dates.push_back(parse_date(token));
        }
        if (comma == std::string::npos) {
            break;
        }
        start = comma + 1;
    }
    return dates;
}

void daily_accrual_preview(
    std::int64_t principal_cents,
    std::int64_t rate_milli_percent,
    std::int64_t months,
    std::int64_t fee_cents,
    const std::string& start_raw,
    const std::string& due_csv
) {
    validate_loan_inputs(principal_cents, rate_milli_percent, months, fee_cents);
    const CivilDate start_date = parse_date(start_raw);
    validate_date(start_date);
    const auto due_dates = parse_due_dates(due_csv);
    for (const auto& due_date : due_dates) {
        validate_date(due_date);
    }
    if (due_dates.size() != static_cast<std::size_t>(months)) {
        throw std::invalid_argument("due date count must match term");
    }

    std::int64_t base_payment_cents = 0;
    if (rate_milli_percent == 0) {
        base_payment_cents = round_ratio_half_up(principal_cents, months);
    } else {
        BigRatio cumulative = normalize_ratio(1, 1);
        BigRatio discount_sum = normalize_ratio(0, 1);
        CivilDate period_start = start_date;
        for (const auto& due_date : due_dates) {
            const BigRatio factor =
                daily_period_factor_ratio(rate_milli_percent, period_start, due_date);
            cumulative = multiply_ratio(
                cumulative,
                add_ratio(normalize_ratio(1, 1), factor)
            );
            discount_sum = add_ratio(discount_sum, reciprocal_ratio(cumulative));
            period_start = due_date;
        }
        if (discount_sum.numerator == 0) {
            throw std::invalid_argument("invalid daily discount sum");
        }
        base_payment_cents = round_big_ratio_half_up(
            cpp_int(principal_cents) * discount_sum.denominator,
            discount_sum.numerator
        );
    }

    const auto fee_parts = split_cents(fee_cents, months);
    std::int64_t opening = principal_cents;
    CivilDate previous_date = start_date;
    __int128 total_interest_wide = 0;
    std::vector<std::int64_t> schedule;
    schedule.reserve(static_cast<std::size_t>(months));

    for (std::int64_t index = 0; index < months; ++index) {
        const auto i = static_cast<std::size_t>(index);
        const std::int64_t interest_due = daily_segment_interest_cents(
            opening, rate_milli_percent, previous_date, due_dates[i]
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
                + static_cast<__int128>(fee_parts[i]),
            "daily schedule row exceeds int64"
        ));
        previous_date = due_dates[i];
    }

    const std::int64_t total_interest_cents =
        checked_i64(total_interest_wide, "daily total interest exceeds int64");
    __int128 total_wide = 0;
    for (const auto value : schedule) {
        total_wide += static_cast<__int128>(value);
    }
    const std::int64_t total_cents =
        checked_i64(total_wide, "daily total exceeds int64");
    emit_preview(schedule.front(), total_interest_cents, total_cents, schedule);
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

        if (argc == 8 && std::string(argv[1]) == "daily-accrual-preview") {
            daily_accrual_preview(
                parse_i64(argv[2]),
                parse_i64(argv[3]),
                parse_i64(argv[4]),
                parse_i64(argv[5]),
                argv[6],
                argv[7]
            );
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
            << "   or: loanhub_native compound-interest-preview <principal_cents> <rate_milli_percent> <months> <fee_cents>\n"
            << "   or: loanhub_native daily-accrual-preview <principal_cents> <rate_milli_percent> <months> <fee_cents> <start_date> <due_dates_csv>\n";
        return 2;
    } catch (...) {
        return 3;
    }
}
