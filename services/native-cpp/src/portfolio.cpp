#include "native.hpp"

namespace loanhub_native {

struct PortfolioCoreSummary {
    std::int64_t active_exposure_cents = 0;
    std::int64_t active_loans = 0;
    std::array<std::int64_t, 5> par_cents{};
    std::int64_t top_up_exposure_cents = 0;
    std::int64_t cdas_exposure_cents = 0;
    std::array<std::int64_t, 6> bucket_counts{};
    std::array<std::int64_t, 6> bucket_exposure_cents{};
};

std::int64_t checked_add_i64(
    std::int64_t left,
    std::int64_t right,
    const char* message
) {
    return checked_i64(
        static_cast<__int128>(left) + static_cast<__int128>(right),
        message
    );
}

int portfolio_bucket_index(const std::string& bucket) {
    if (bucket == "current") return 0;
    if (bucket == "1-7") return 1;
    if (bucket == "8-30") return 2;
    if (bucket == "31-60") return 3;
    if (bucket == "61-90") return 4;
    if (bucket == "90+") return 5;
    return -1;
}

void portfolio_risk_core() {
    PortfolioCoreSummary summary;
    std::string line;
    const std::array<std::int64_t, 5> thresholds{1, 7, 30, 60, 90};

    while (std::getline(std::cin, line)) {
        if (line.empty()) {
            continue;
        }
        std::vector<std::string> fields;
        std::size_t start = 0;
        while (start <= line.size()) {
            const std::size_t separator = line.find('|', start);
            fields.push_back(line.substr(
                start,
                separator == std::string::npos ? std::string::npos : separator - start
            ));
            if (separator == std::string::npos) {
                break;
            }
            start = separator + 1;
        }
        if (fields.size() != 6) {
            throw std::invalid_argument("invalid portfolio row");
        }

        const std::int64_t balance_cents = std::stoll(fields[0]);
        const std::int64_t days_past_due = std::stoll(fields[1]);
        const bool active = fields[2] == "1";
        const bool is_top_up = fields[3] == "1";
        const bool cdas_enabled = fields[4] == "1";
        const int bucket_index = portfolio_bucket_index(fields[5]);

        if (balance_cents < 0) {
            throw std::invalid_argument("negative portfolio balance");
        }
        if (!active) {
            continue;
        }

        summary.active_loans = checked_add_i64(
            summary.active_loans, 1, "active loan count exceeds int64"
        );
        summary.active_exposure_cents = checked_add_i64(
            summary.active_exposure_cents,
            balance_cents,
            "active exposure exceeds int64"
        );
        for (std::size_t i = 0; i < thresholds.size(); ++i) {
            if (days_past_due >= thresholds[i]) {
                summary.par_cents[i] = checked_add_i64(
                    summary.par_cents[i],
                    balance_cents,
                    "portfolio PAR amount exceeds int64"
                );
            }
        }
        if (is_top_up) {
            summary.top_up_exposure_cents = checked_add_i64(
                summary.top_up_exposure_cents,
                balance_cents,
                "top-up exposure exceeds int64"
            );
        }
        if (cdas_enabled) {
            summary.cdas_exposure_cents = checked_add_i64(
                summary.cdas_exposure_cents,
                balance_cents,
                "CDAS exposure exceeds int64"
            );
        }
        if (bucket_index >= 0) {
            const auto index = static_cast<std::size_t>(bucket_index);
            summary.bucket_counts[index] = checked_add_i64(
                summary.bucket_counts[index],
                1,
                "bucket count exceeds int64"
            );
            summary.bucket_exposure_cents[index] = checked_add_i64(
                summary.bucket_exposure_cents[index],
                balance_cents,
                "bucket exposure exceeds int64"
            );
        }
    }

    std::cout
        << summary.active_exposure_cents << "|"
        << summary.active_loans;
    for (const auto value : summary.par_cents) {
        std::cout << "|" << value;
    }
    std::cout
        << "|" << summary.top_up_exposure_cents
        << "|" << summary.cdas_exposure_cents;
    for (std::size_t i = 0; i < summary.bucket_counts.size(); ++i) {
        std::cout
            << "|" << summary.bucket_counts[i]
            << "|" << summary.bucket_exposure_cents[i];
    }
    std::cout << "\n";
}


struct ConcentrationAggregate {
    std::int64_t loan_count = 0;
    std::int64_t exposure_cents = 0;
    std::int64_t par30_cents = 0;
    std::int64_t fpd_eligible = 0;
    std::int64_t fpd_count = 0;
};

struct VintageAggregate {
    std::int64_t loan_count = 0;
    std::int64_t originated_cents = 0;
    std::int64_t outstanding_cents = 0;
    std::int64_t par30_cents = 0;
    std::int64_t fpd_eligible = 0;
    std::int64_t fpd_count = 0;
    std::int64_t write_off_count = 0;
    std::int64_t top_up_count = 0;
};

struct TopUpAggregate {
    std::int64_t loan_count = 0;
    std::int64_t active_exposure_cents = 0;
    std::int64_t par30_cents = 0;
    std::int64_t fpd_eligible = 0;
    std::int64_t fpd_count = 0;
    std::int64_t write_off_count = 0;
};

void add_concentration_row(
    std::map<std::int64_t, ConcentrationAggregate>& groups,
    std::int64_t label_id,
    std::int64_t balance_cents,
    std::int64_t days_past_due,
    bool first_payment_due,
    bool first_payment_default
) {
    auto& group = groups[label_id];
    group.loan_count = checked_add_i64(group.loan_count, 1, "group loan count exceeds int64");
    group.exposure_cents = checked_add_i64(
        group.exposure_cents, balance_cents, "group exposure exceeds int64"
    );
    if (days_past_due >= 30) {
        group.par30_cents = checked_add_i64(
            group.par30_cents, balance_cents, "group par30 exceeds int64"
        );
    }
    if (first_payment_due) {
        group.fpd_eligible = checked_add_i64(
            group.fpd_eligible, 1, "group fpd eligible exceeds int64"
        );
        if (first_payment_default) {
            group.fpd_count = checked_add_i64(
                group.fpd_count, 1, "group fpd count exceeds int64"
            );
        }
    }
}

void portfolio_risk_groups() {
    std::map<std::int64_t, ConcentrationAggregate> branches;
    std::map<std::int64_t, ConcentrationAggregate> products;
    std::map<std::int64_t, ConcentrationAggregate> employers;
    std::map<std::string, VintageAggregate> vintages;
    std::array<TopUpAggregate, 2> topups{};

    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) {
            continue;
        }
        std::vector<std::string> fields;
        std::size_t start = 0;
        while (start <= line.size()) {
            const std::size_t separator = line.find('|', start);
            fields.push_back(line.substr(
                start,
                separator == std::string::npos ? std::string::npos : separator - start
            ));
            if (separator == std::string::npos) {
                break;
            }
            start = separator + 1;
        }
        if (fields.size() != 13) {
            throw std::invalid_argument("invalid portfolio group row");
        }

        const std::int64_t balance_cents = std::stoll(fields[0]);
        const std::int64_t principal_cents = std::stoll(fields[1]);
        const std::int64_t days_past_due = std::stoll(fields[2]);
        const bool active = fields[3] == "1";
        const bool is_written_off = fields[4] == "1";
        const bool is_top_up = fields[5] == "1";
        const bool first_payment_due = fields[6] == "1";
        const bool first_payment_default = fields[7] == "1";
        const std::int64_t branch_id = std::stoll(fields[8]);
        const std::int64_t product_id = std::stoll(fields[9]);
        const std::int64_t employer_id = std::stoll(fields[10]);
        const bool has_vintage = fields[11] == "1";
        const std::string vintage = fields[12];

        if (balance_cents < 0 || principal_cents < 0) {
            throw std::invalid_argument("negative portfolio amount");
        }

        if (active) {
            add_concentration_row(
                branches, branch_id, balance_cents, days_past_due,
                first_payment_due, first_payment_default
            );
            add_concentration_row(
                products, product_id, balance_cents, days_past_due,
                first_payment_due, first_payment_default
            );
            add_concentration_row(
                employers, employer_id, balance_cents, days_past_due,
                first_payment_due, first_payment_default
            );
        }

        if (has_vintage) {
            auto& item = vintages[vintage];
            item.loan_count = checked_add_i64(item.loan_count, 1, "vintage count exceeds int64");
            item.originated_cents = checked_add_i64(
                item.originated_cents, principal_cents, "vintage originated exceeds int64"
            );
            if (!is_written_off) {
                item.outstanding_cents = checked_add_i64(
                    item.outstanding_cents, balance_cents, "vintage outstanding exceeds int64"
                );
                if (days_past_due >= 30) {
                    item.par30_cents = checked_add_i64(
                        item.par30_cents, balance_cents, "vintage par30 exceeds int64"
                    );
                }
            }
            if (first_payment_due) {
                item.fpd_eligible = checked_add_i64(
                    item.fpd_eligible, 1, "vintage fpd eligible exceeds int64"
                );
                if (first_payment_default) {
                    item.fpd_count = checked_add_i64(
                        item.fpd_count, 1, "vintage fpd count exceeds int64"
                    );
                }
            }
            if (is_written_off) {
                item.write_off_count = checked_add_i64(
                    item.write_off_count, 1, "vintage write-off count exceeds int64"
                );
            }
            if (is_top_up) {
                item.top_up_count = checked_add_i64(
                    item.top_up_count, 1, "vintage top-up count exceeds int64"
                );
            }
        }

        auto& topup = topups[is_top_up ? 1 : 0];
        topup.loan_count = checked_add_i64(
            topup.loan_count, 1, "top-up group count exceeds int64"
        );
        if (active) {
            topup.active_exposure_cents = checked_add_i64(
                topup.active_exposure_cents,
                balance_cents,
                "top-up active exposure exceeds int64"
            );
            if (days_past_due >= 30) {
                topup.par30_cents = checked_add_i64(
                    topup.par30_cents, balance_cents, "top-up par30 exceeds int64"
                );
            }
        }
        if (first_payment_due) {
            topup.fpd_eligible = checked_add_i64(
                topup.fpd_eligible, 1, "top-up fpd eligible exceeds int64"
            );
            if (first_payment_default) {
                topup.fpd_count = checked_add_i64(
                    topup.fpd_count, 1, "top-up fpd count exceeds int64"
                );
            }
        }
        if (is_written_off) {
            topup.write_off_count = checked_add_i64(
                topup.write_off_count, 1, "top-up write-off count exceeds int64"
            );
        }
    }

    const auto emit_concentration = [](
        const char dimension,
        const std::map<std::int64_t, ConcentrationAggregate>& groups
    ) {
        for (const auto& [label_id, item] : groups) {
            std::cout
                << "C|" << dimension << "|" << label_id
                << "|" << item.loan_count
                << "|" << item.exposure_cents
                << "|" << item.par30_cents
                << "|" << item.fpd_eligible
                << "|" << item.fpd_count << "\n";
        }
    };
    emit_concentration('B', branches);
    emit_concentration('P', products);
    emit_concentration('E', employers);

    for (const auto& [month, item] : vintages) {
        std::cout
            << "V|" << month
            << "|" << item.loan_count
            << "|" << item.originated_cents
            << "|" << item.outstanding_cents
            << "|" << item.par30_cents
            << "|" << item.fpd_eligible
            << "|" << item.fpd_count
            << "|" << item.write_off_count
            << "|" << item.top_up_count << "\n";
    }

    for (std::size_t index = 0; index < topups.size(); ++index) {
        const auto& item = topups[index];
        std::cout
            << "T|" << index
            << "|" << item.loan_count
            << "|" << item.active_exposure_cents
            << "|" << item.par30_cents
            << "|" << item.fpd_eligible
            << "|" << item.fpd_count
            << "|" << item.write_off_count << "\n";
    }
}

} // namespace loanhub_native
