#include "accounting.hpp"
#include <cassert>
#include <limits>
#include <stdexcept>
#include <vector>
using namespace loanhub_native::accounting;
template <typename Action> bool throws(Action action) {
    try { action(); } catch (const std::exception&) { return true; }
    return false;
}
int main() {
    const std::vector<JournalLine> posted{{101, 10000, 0}, {201, 0, 10000}};
    validate_journal(posted);
    const auto trial = calculate_trial_balance(posted);
    assert(trial.debit_cents == 10000 && trial.credit_cents == 10000);
    assert(trial.accounts.size() == 2);
    assert(trial.accounts[0].net_debit_cents == 10000);
    assert(trial.accounts[1].net_debit_cents == -10000);
    assert(throws([] { validate_journal({{101, 10000, 0}, {201, 0, 9999}}); }));
    assert(throws([] { validate_journal({{101, -1, 0}, {201, 0, 1}}); }));
    assert(throws([] { validate_journal({{101, 100, 100}, {201, 0, 100}}); }));
    assert(throws([] { validate_journal({{101, 0, 0}, {201, 0, 1}}); }));
    assert(throws([] { validate_journal({{101, 1, 0}}); }));
    assert(throws([] {
        const auto max = std::numeric_limits<std::int64_t>::max();
        calculate_trial_balance({{101, max, 0}, {101, max, 0}});
    }));
    return 0;
}
