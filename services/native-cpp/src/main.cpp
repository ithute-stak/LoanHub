#include "native.hpp"
using namespace loanhub_native;

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "predictive-risk-batch") {
            predictive_risk_batch();
            return 0;
        }

        if (argc == 13 && std::string(argv[1]) == "predictive-risk-signal") {
            predictive_risk_signal(
                parse_i64(argv[2]),
                parse_i64(argv[3]) != 0,
                parse_i64(argv[4]),
                argv[5],
                parse_i64(argv[6]) != 0,
                argv[7],
                parse_i64(argv[8]) != 0,
                parse_i64(argv[9]) != 0,
                parse_i64(argv[10]) != 0,
                argv[11],
                parse_i64(argv[12])
            );
            return 0;
        }

        if (argc == 4 && std::string(argv[1]) == "reconciliation-variance") {
            reconciliation_variance(parse_i64(argv[2]), parse_i64(argv[3]));
            return 0;
        }

        if (argc == 2 && std::string(argv[1]) == "portfolio-risk-core") {
            portfolio_risk_core();
            return 0;
        }

        if (argc == 2 && std::string(argv[1]) == "portfolio-risk-groups") {
            portfolio_risk_groups();
            return 0;
        }

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
            << "usage: loanhub_native predictive-risk-batch < stdin_rows\n"
            << "   or: loanhub_native predictive-risk-signal <current_dpd> <has_previous_dpd> <previous_dpd> <current_bucket> <has_previous_bucket> <previous_bucket> <first_payment_default> <is_top_up> <has_work_item> <work_priority> <work_priority_score_milli>\n"
            << "   or: loanhub_native reconciliation-variance <expected_cents> <actual_cents>\n"
            << "   or: loanhub_native portfolio-risk-core < stdin_rows\n"
            << "   or: loanhub_native portfolio-risk-groups < stdin_rows\n"
            << "   or: loanhub_native simple-interest <principal_cents> <rate_milli_percent> <months>\n"
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
