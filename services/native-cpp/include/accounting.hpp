#pragma once
#include <cstdint>
#include <vector>
namespace loanhub_native::accounting {
struct JournalLine {
    std::int64_t account_id;
    std::int64_t debit_cents;
    std::int64_t credit_cents;
};
struct AccountTotal {
    std::int64_t account_id;
    std::int64_t debit_cents;
    std::int64_t credit_cents;
    std::int64_t net_debit_cents;
};
struct TrialBalance {
    std::int64_t debit_cents;
    std::int64_t credit_cents;
    std::vector<AccountTotal> accounts;
};
void validate_journal(const std::vector<JournalLine>& lines);
TrialBalance calculate_trial_balance(const std::vector<JournalLine>& lines);
} // namespace loanhub_native::accounting
