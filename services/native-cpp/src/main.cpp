#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

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

}  // namespace

int main(int argc, char** argv) {
    try {
        // Exact cents kernel used only behind Rust + Python parity:
        // simple-interest <principal_cents> <rate_milli_percent> <months>
        //
        // rate_milli_percent: 36.125% => 36125
        if (argc == 5 && std::string(argv[1]) == "simple-interest") {
            const std::int64_t principal_cents = parse_i64(argv[2]);
            const std::int64_t rate_milli_percent = parse_i64(argv[3]);
            const std::int64_t months = parse_i64(argv[4]);
            if (principal_cents < 0 || rate_milli_percent < 0 || months <= 0 || months > 120) {
                return 2;
            }

            // principal * (rate / 100) * (months / 12)
            // rate_milli_percent is percent * 1000.
            const __int128 numerator =
                static_cast<__int128>(principal_cents)
                * static_cast<__int128>(rate_milli_percent)
                * static_cast<__int128>(months);
            const __int128 denominator = static_cast<__int128>(1000) * 100 * 12;
            std::cout << round_ratio_half_up(numerator, denominator) << "\n";
            return 0;
        }

        std::cerr << "usage: loanhub_native simple-interest <principal_cents> <rate_milli_percent> <months>\n";
        return 2;
    } catch (...) {
        return 3;
    }
}
