#include "native.hpp"
using namespace loanhub_native;

extern "C" int loanhub_native_execute(
    const char* command_raw,
    const char* payload_raw,
    char* output,
    std::size_t output_capacity
) {
    static std::mutex execution_mutex;
    if (command_raw == nullptr || payload_raw == nullptr) {
        return -1;
    }

    std::lock_guard<std::mutex> lock(execution_mutex);
    const std::string command(command_raw);
    const std::string payload(payload_raw);
    std::istringstream input_stream(payload);
    std::ostringstream output_stream;
    const auto prior_input_state = std::cin.rdstate();
    const auto prior_output_state = std::cout.rdstate();
    std::cin.clear();
    std::cout.clear();
    auto* prior_input = std::cin.rdbuf(input_stream.rdbuf());
    auto* prior_output = std::cout.rdbuf(output_stream.rdbuf());

    int status = 0;
    try {
        const auto split_payload = [](const std::string& raw) {
            std::vector<std::string> fields;
            std::size_t start = 0;
            while (start <= raw.size()) {
                const std::size_t separator = raw.find('|', start);
                fields.push_back(raw.substr(
                    start,
                    separator == std::string::npos
                        ? std::string::npos
                        : separator - start
                ));
                if (separator == std::string::npos) {
                    break;
                }
                start = separator + 1;
            }
            return fields;
        };

        if (command == "simple-flat-preview"
            || command == "micro-loan-preview"
            || command == "reducing-balance-preview"
            || command == "compound-interest-preview") {
            const auto fields = split_payload(payload);
            if (fields.size() != 4) {
                status = -1;
            } else {
                const std::int64_t principal_cents = std::stoll(fields[0]);
                const std::int64_t rate_milli_percent = std::stoll(fields[1]);
                const std::int64_t months = std::stoll(fields[2]);
                const std::int64_t fee_cents = std::stoll(fields[3]);
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
            }
        } else if (command == "daily-accrual-preview") {
            const auto fields = split_payload(payload);
            if (fields.size() != 6) {
                status = -1;
            } else {
                daily_accrual_preview(
                    std::stoll(fields[0]),
                    std::stoll(fields[1]),
                    std::stoll(fields[2]),
                    std::stoll(fields[3]),
                    fields[4],
                    fields[5]
                );
            }
        } else if (command == "portfolio-risk-core") {
            portfolio_risk_core();
        } else if (command == "portfolio-risk-groups") {
            portfolio_risk_groups();
        } else if (command == "predictive-risk-batch") {
            predictive_risk_batch();
        } else if (command == "reconciliation-variance") {
            const auto fields = split_payload(payload);
            if (fields.size() != 2) {
                status = -1;
            } else {
                reconciliation_variance(
                    std::stoll(fields[0]),
                    std::stoll(fields[1])
                );
            }
        } else {
            status = -1;
        }
    } catch (...) {
        status = -3;
    }

    std::cin.rdbuf(prior_input);
    std::cout.rdbuf(prior_output);
    std::cin.clear(prior_input_state);
    std::cout.clear(prior_output_state);

    if (status != 0) {
        return status;
    }

    const std::string result = output_stream.str();
    if (output == nullptr || output_capacity <= result.size()) {
        return -2;
    }
    std::memcpy(output, result.data(), result.size());
    output[result.size()] = '\0';
    return static_cast<int>(result.size());
}
