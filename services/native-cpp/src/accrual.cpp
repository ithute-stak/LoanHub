#include "native.hpp"

namespace loanhub_native {

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

} // namespace loanhub_native
