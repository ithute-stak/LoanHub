#include "native.hpp"

namespace loanhub_native {

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

} // namespace loanhub_native
