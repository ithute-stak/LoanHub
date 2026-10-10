#include "native.hpp"

namespace loanhub_native {

std::int64_t saturating_sub_i64(std::int64_t left, std::int64_t right) {
    const __int128 value =
        static_cast<__int128>(left) - static_cast<__int128>(right);
    if (value > std::numeric_limits<std::int64_t>::max()) {
        return std::numeric_limits<std::int64_t>::max();
    }
    if (value < std::numeric_limits<std::int64_t>::min()) {
        return std::numeric_limits<std::int64_t>::min();
    }
    return static_cast<std::int64_t>(value);
}

void reconciliation_variance(
    std::int64_t expected_cents,
    std::int64_t actual_cents
) {
    const std::int64_t variance =
        saturating_sub_i64(actual_cents, expected_cents);
    const char* status =
        variance == 0 ? "matched" : variance < 0 ? "shortage" : "excess";
    std::cout << status << "|" << variance << "\n";
}

} // namespace loanhub_native
