#include "native.hpp"

namespace loanhub_native {

std::int64_t predictive_bucket_rank(const std::string& value) {
    if (value == "1-7") return 1;
    if (value == "8-30") return 2;
    if (value == "31-60") return 3;
    if (value == "61-90") return 4;
    if (value == "90+") return 5;
    return 0;
}

const char* predictive_band_name(std::int64_t score) {
    if (score >= 80) return "critical";
    if (score >= 60) return "high";
    if (score >= 40) return "elevated";
    if (score >= 20) return "watch";
    return "stable";
}

const char* predictive_bucket_name(std::int64_t days) {
    if (days <= 0) return "current";
    if (days <= 7) return "1-7";
    if (days <= 30) return "8-30";
    if (days <= 60) return "31-60";
    if (days <= 90) return "61-90";
    return "90+";
}

struct PredictiveRiskResult {
    std::int64_t score;
    std::string band;
    bool projected_par30;
    std::string stress_bucket;
    std::uint64_t reasons;
    bool has_change;
    std::int64_t change;
};

PredictiveRiskResult predictive_risk_result(
    std::int64_t current_dpd,
    bool has_previous_dpd,
    std::int64_t previous_dpd,
    const std::string& current_bucket,
    bool has_previous_bucket,
    const std::string& previous_bucket,
    bool first_payment_default,
    bool is_top_up,
    bool has_work_item,
    const std::string& work_priority,
    std::int64_t work_priority_score_milli
) {
    std::int64_t score = 0;
    std::uint64_t reasons = 0;

    if (current_dpd >= 90) {
        score += 75;
        reasons |= (1ULL << 0);
    } else if (current_dpd >= 60) {
        score += 60;
        reasons |= (1ULL << 0);
    } else if (current_dpd >= 30) {
        score += 45;
        reasons |= (1ULL << 0);
    } else if (current_dpd >= 8) {
        score += 25;
        reasons |= (1ULL << 1);
    } else if (current_dpd >= 1) {
        score += 12;
        reasons |= (1ULL << 2);
    }

    bool has_change = false;
    std::int64_t change = 0;
    if (has_previous_dpd) {
        change = saturating_sub_i64(current_dpd, previous_dpd);
        has_change = true;
        if (change >= 15) {
            score += 15;
            reasons |= (1ULL << 3);
        } else if (change >= 7) {
            score += 10;
            reasons |= (1ULL << 3);
        }
    }

    if (
        has_previous_bucket
        && previous_bucket != current_bucket
        && predictive_bucket_rank(current_bucket) > predictive_bucket_rank(previous_bucket)
    ) {
        score += 8;
        reasons |= (1ULL << 4);
    }

    if (first_payment_default) {
        score += 20;
        reasons |= (1ULL << 5);
    }
    if (is_top_up && current_dpd > 0) {
        score += 5;
        reasons |= (1ULL << 6);
    }

    if (has_work_item) {
        if (work_priority == "critical" || work_priority == "urgent") {
            score += 10;
            reasons |= (1ULL << 7);
        } else if (
            work_priority == "high"
            || work_priority_score_milli >= 70'000
        ) {
            score += 6;
            reasons |= (1ULL << 8);
        }
    }

    if (score > 100) {
        score = 100;
    }

    const bool projected_par30 =
        current_dpd >= 1
        && current_dpd < 30
        && (
            current_dpd >= 8
            || first_payment_default
            || (has_change && change >= 7)
        );

    const std::int64_t stress_days =
        current_dpd > 0
            ? (
                current_dpd > std::numeric_limits<std::int64_t>::max() - 30
                    ? std::numeric_limits<std::int64_t>::max()
                    : current_dpd + 30
            )
            : current_dpd;

    return PredictiveRiskResult{
        score,
        predictive_band_name(score),
        projected_par30,
        current_dpd > 0 ? predictive_bucket_name(stress_days) : current_bucket,
        reasons,
        has_change,
        change,
    };
}

void emit_predictive_risk_result(const PredictiveRiskResult& result) {
    std::cout
        << result.score << "|"
        << result.band << "|"
        << (result.projected_par30 ? 1 : 0) << "|"
        << result.stress_bucket << "|"
        << result.reasons << "|"
        << (result.has_change ? 1 : 0) << "|"
        << result.change << "\n";
}

void predictive_risk_signal(
    std::int64_t current_dpd,
    bool has_previous_dpd,
    std::int64_t previous_dpd,
    const std::string& current_bucket,
    bool has_previous_bucket,
    const std::string& previous_bucket,
    bool first_payment_default,
    bool is_top_up,
    bool has_work_item,
    const std::string& work_priority,
    std::int64_t work_priority_score_milli
) {
    emit_predictive_risk_result(predictive_risk_result(
        current_dpd,
        has_previous_dpd,
        previous_dpd,
        current_bucket,
        has_previous_bucket,
        previous_bucket,
        first_payment_default,
        is_top_up,
        has_work_item,
        work_priority,
        work_priority_score_milli
    ));
}

void predictive_risk_batch() {
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
        if (fields.size() != 11) {
            throw std::invalid_argument("invalid predictive risk row");
        }
        emit_predictive_risk_result(predictive_risk_result(
            std::stoll(fields[0]),
            fields[1] == "1",
            std::stoll(fields[2]),
            fields[3],
            fields[4] == "1",
            fields[5],
            fields[6] == "1",
            fields[7] == "1",
            fields[8] == "1",
            fields[9],
            std::stoll(fields[10])
        ));
    }
}

} // namespace loanhub_native
