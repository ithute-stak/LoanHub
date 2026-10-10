#pragma once
#include <boost/multiprecision/cpp_int.hpp>
#include <algorithm>
#include <array>
#include <map>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace loanhub_native {
using boost::multiprecision::cpp_int;
inline constexpr std::int64_t MONTHLY_RATE_DENOMINATOR = 1'200'000;
std::int64_t parse_i64(const char*);
std::int64_t round_ratio_half_up(__int128, __int128);
std::int64_t round_big_ratio_half_up(cpp_int, const cpp_int&);
cpp_int pow_int(cpp_int, std::int64_t);
std::vector<std::int64_t> split_cents(std::int64_t, std::int64_t);
std::int64_t checked_i64(__int128, const char*);
void emit_preview(std::int64_t, std::int64_t, std::int64_t, const std::vector<std::int64_t>&);
void simple_flat_preview(std::int64_t, std::int64_t, std::int64_t, std::int64_t);
void micro_loan_preview(std::int64_t, std::int64_t, std::int64_t, std::int64_t);
void reducing_balance_preview(std::int64_t, std::int64_t, std::int64_t, std::int64_t);
void compound_interest_preview(std::int64_t, std::int64_t, std::int64_t, std::int64_t);
void daily_accrual_preview(std::int64_t, std::int64_t, std::int64_t, std::int64_t, const std::string&, const std::string&);
void portfolio_risk_core();
void portfolio_risk_groups();
std::int64_t saturating_sub_i64(std::int64_t, std::int64_t);
void reconciliation_variance(std::int64_t, std::int64_t);
void predictive_risk_signal(std::int64_t, bool, std::int64_t, const std::string&, bool, const std::string&, bool, bool, bool, const std::string&, std::int64_t);
void predictive_risk_batch();
}
