#include "accounting.hpp"
#include <limits>
#include <map>
#include <stdexcept>
namespace loanhub_native::accounting {
namespace {
std::int64_t checked(const __int128 value) {
    if (value > std::numeric_limits<std::int64_t>::max()
        || value < std::numeric_limits<std::int64_t>::min()) {
        throw std::overflow_error("accounting total exceeds int64");
    }
    return static_cast<std::int64_t>(value);
}
void validate_line(const JournalLine& line) {
    if (line.account_id <= 0 || line.debit_cents < 0 || line.credit_cents < 0
        || (line.debit_cents == 0 && line.credit_cents == 0)
        || (line.debit_cents != 0 && line.credit_cents != 0)) {
        throw std::invalid_argument("invalid journal line");
    }
}
}
void validate_journal(const std::vector<JournalLine>& lines) {
    if (lines.size() < 2) throw std::invalid_argument("journal requires two or more lines");
    __int128 debits = 0, credits = 0;
    for (const auto& line : lines) {
        validate_line(line);
        debits += line.debit_cents;
        credits += line.credit_cents;
    }
    checked(debits);
    checked(credits);
    if (debits != credits) throw std::invalid_argument("unbalanced journal");
}
TrialBalance calculate_trial_balance(const std::vector<JournalLine>& lines) {
    std::map<std::int64_t, std::pair<__int128, __int128>> totals;
    __int128 debits = 0, credits = 0;
    for (const auto& line : lines) {
        validate_line(line);
        auto& total = totals[line.account_id];
        total.first += line.debit_cents;
        total.second += line.credit_cents;
        debits += line.debit_cents;
        credits += line.credit_cents;
    }
    TrialBalance result{checked(debits), checked(credits), {}};
    for (const auto& [account, total] : totals) {
        result.accounts.push_back(AccountTotal{
            account, checked(total.first), checked(total.second),
            checked(total.first - total.second)
        });
    }
    return result;
}
} // namespace loanhub_native::accounting
