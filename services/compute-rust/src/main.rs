use chrono::{Datelike, Duration, NaiveDate};
use rust_decimal::prelude::*;
use rust_decimal::RoundingStrategy;
use serde::{Deserialize, Serialize};
use std::env;
use std::io::Read;
use std::process::Command;
use tiny_http::{Header, Method, Response, Server, StatusCode};

fn money(value: Decimal) -> Decimal {
    value.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero)
}

fn split_amount(total: Decimal, count: usize) -> Vec<Decimal> {
    let total = money(total);
    let regular = money(total / Decimal::from(count as i64));
    let mut values = vec![regular; count];
    if count > 0 {
        let prior = values[..count.saturating_sub(1)]
            .iter()
            .copied()
            .fold(Decimal::ZERO, |acc, value| acc + value);
        values[count - 1] = money(total - prior);
    }
    values
}

#[derive(Debug, Deserialize)]
struct LoanPreviewRequest {
    method: String,
    principal: String,
    rate_percent: String,
    term_months: usize,
    processing_fee: String,
    interest_start_date: Option<String>,
    due_dates: Vec<String>,
}

#[derive(Debug, Serialize)]
struct LoanPreviewResponse {
    method: String,
    monthly_installment: String,
    total_interest: String,
    total_repayable: String,
    schedule_amounts: Vec<String>,
    authoritative: bool,
    native_cpp_used: bool,
}

fn decimal(value: &str) -> Result<Decimal, String> {
    value.parse::<Decimal>().map_err(|_| format!("invalid decimal: {value}"))
}

fn micro_loan(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate = decimal(&req.rate_percent)?;
    let fee = money(decimal(&req.processing_fee)?);
    let factor = Decimal::ONE + rate / Decimal::from(100_i64);
    let mut running = principal;
    let mut components: Vec<Decimal> = Vec::with_capacity(req.term_months);
    for month in 0..req.term_months {
        let amount_after_rate = money(running * factor);
        let component = if month + 1 < req.term_months {
            money(amount_after_rate / Decimal::from(2_i64))
        } else {
            amount_after_rate
        };
        running = if month + 1 < req.term_months {
            money(amount_after_rate - component)
        } else {
            Decimal::ZERO
        };
        components.push(component);
    }
    let total = money(components.iter().copied().sum::<Decimal>() + fee);
    let schedule = split_amount(total, req.term_months);
    let total_interest = money(total - principal - fee);
    Ok(LoanPreviewResponse {
        method: req.method.clone(),
        monthly_installment: schedule.first().copied().unwrap_or(Decimal::ZERO).to_string(),
        total_interest: total_interest.to_string(),
        total_repayable: total.to_string(),
        schedule_amounts: schedule.into_iter().map(|v| v.to_string()).collect(),
        authoritative: false,
        native_cpp_used: false,
    })
}

fn cpp_simple_interest_cents(
    principal: Decimal,
    rate_percent: Decimal,
    months: usize,
) -> Option<i64> {
    if rate_percent.scale() > 3 {
        return None;
    }
    let path = env::var("LOANHUB_CPP_KERNEL_PATH").ok()?;
    let principal_cents = (money(principal) * Decimal::from(100_i64)).to_i64()?;
    let rate_milli_percent = (
        rate_percent.round_dp_with_strategy(3, RoundingStrategy::MidpointAwayFromZero)
            * Decimal::from(1000_i64)
    ).to_i64()?;
    let output = Command::new(path)
        .arg("simple-interest")
        .arg(principal_cents.to_string())
        .arg(rate_milli_percent.to_string())
        .arg(months.to_string())
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout).ok()?.trim().parse::<i64>().ok()
}

fn simple_or_flat(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate_percent = decimal(&req.rate_percent)?;
    let fee = money(decimal(&req.processing_fee)?);
    let annual_rate = rate_percent / Decimal::from(100_i64);
    let rust_total_interest = money(
        principal * annual_rate * Decimal::from(req.term_months as i64) / Decimal::from(12_i64),
    );
    let rust_interest_cents = (rust_total_interest * Decimal::from(100_i64)).to_i64();
    let cpp_interest_cents = cpp_simple_interest_cents(principal, rate_percent, req.term_months);
    let native_cpp_used = cpp_interest_cents.is_some()
        && rust_interest_cents.is_some()
        && cpp_interest_cents == rust_interest_cents;
    let total_interest = if native_cpp_used {
        money(
            Decimal::from(cpp_interest_cents.unwrap_or_default())
                / Decimal::from(100_i64)
        )
    } else {
        rust_total_interest
    };
    let total = money(principal + total_interest + fee);
    let principal_parts = split_amount(principal, req.term_months);
    let interest_parts = split_amount(total_interest, req.term_months);
    let fee_parts = split_amount(fee, req.term_months);
    let schedule: Vec<Decimal> = (0..req.term_months)
        .map(|i| money(principal_parts[i] + interest_parts[i] + fee_parts[i]))
        .collect();
    Ok(LoanPreviewResponse {
        method: req.method.clone(),
        monthly_installment: schedule.first().copied().unwrap_or(Decimal::ZERO).to_string(),
        total_interest: total_interest.to_string(),
        total_repayable: total.to_string(),
        schedule_amounts: schedule.into_iter().map(|v| v.to_string()).collect(),
        authoritative: false,
        native_cpp_used,
    })
}

fn reducing_balance(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate_percent = decimal(&req.rate_percent)?;
    let fee = money(decimal(&req.processing_fee)?);
    let monthly_rate =
        (rate_percent / Decimal::from(100_i64)) / Decimal::from(12_i64);

    let base_payment = if monthly_rate.is_zero() {
        money(principal / Decimal::from(req.term_months as i64))
    } else {
        let mut growth = Decimal::ONE;
        for _ in 0..req.term_months {
            growth *= Decimal::ONE + monthly_rate;
        }
        let denominator = growth - Decimal::ONE;
        if denominator.is_zero() {
            return Err("invalid_amortisation_denominator".to_string());
        }
        money(principal * monthly_rate * growth / denominator)
    };

    let fee_parts = split_amount(fee, req.term_months);
    let mut opening = principal;
    let mut total_interest = Decimal::ZERO;
    let mut schedule: Vec<Decimal> = Vec::with_capacity(req.term_months);

    for index in 0..req.term_months {
        let interest_due = money(opening * monthly_rate);
        let principal_due = if index + 1 == req.term_months {
            opening
        } else {
            let candidate = money(base_payment - interest_due);
            let non_negative = if candidate < Decimal::ZERO {
                Decimal::ZERO
            } else {
                candidate
            };
            if non_negative > opening { opening } else { non_negative }
        };
        let closing_candidate = money(opening - principal_due);
        let closing = if closing_candidate < Decimal::ZERO {
            Decimal::ZERO
        } else {
            closing_candidate
        };
        let total_due = money(principal_due + interest_due + fee_parts[index]);
        total_interest += interest_due;
        schedule.push(total_due);
        opening = closing;
    }

    let total_interest = money(total_interest);
    let total = money(schedule.iter().copied().sum::<Decimal>());
    Ok(LoanPreviewResponse {
        method: req.method.clone(),
        monthly_installment: schedule.first().copied().unwrap_or(Decimal::ZERO).to_string(),
        total_interest: total_interest.to_string(),
        total_repayable: total.to_string(),
        schedule_amounts: schedule.into_iter().map(|v| v.to_string()).collect(),
        authoritative: false,
        native_cpp_used: false,
    })
}

fn parse_date(value: &str) -> Result<NaiveDate, String> {
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .map_err(|_| format!("invalid date: {value}"))
}

fn month_days(year: i32, month: u32) -> Result<u32, String> {
    let (next_year, next_month) = if month == 12 {
        (year + 1, 1)
    } else {
        (year, month + 1)
    };
    let next = NaiveDate::from_ymd_opt(next_year, next_month, 1)
        .ok_or_else(|| "invalid month".to_string())?;
    Ok((next - Duration::days(1)).day())
}

fn daily_period_factor(
    annual_rate: Decimal,
    start_date: NaiveDate,
    end_date: NaiveDate,
) -> Result<Decimal, String> {
    if annual_rate.is_zero() || end_date <= start_date {
        return Ok(Decimal::ZERO);
    }
    let monthly_rate = annual_rate / Decimal::from(12_i64);
    let mut current = start_date + Duration::days(1);
    let mut factor = Decimal::ZERO;
    while current <= end_date {
        let days_in_month = month_days(current.year(), current.month())?;
        let month_end = NaiveDate::from_ymd_opt(current.year(), current.month(), days_in_month)
            .ok_or_else(|| "invalid month end".to_string())?;
        let segment_end = if month_end < end_date { month_end } else { end_date };
        let days = (segment_end - current).num_days() + 1;
        factor += monthly_rate * Decimal::from(days) / Decimal::from(days_in_month);
        current = segment_end + Duration::days(1);
    }
    Ok(factor)
}

fn daily_segment_interest(
    balance: Decimal,
    annual_rate: Decimal,
    start_date: NaiveDate,
    end_date: NaiveDate,
) -> Result<Decimal, String> {
    if annual_rate.is_zero() || end_date <= start_date {
        return Ok(Decimal::ZERO);
    }
    let monthly_rate = annual_rate / Decimal::from(12_i64);
    let mut current = start_date + Duration::days(1);
    let mut total = Decimal::ZERO;
    while current <= end_date {
        let days_in_month = month_days(current.year(), current.month())?;
        let month_end = NaiveDate::from_ymd_opt(current.year(), current.month(), days_in_month)
            .ok_or_else(|| "invalid month end".to_string())?;
        let segment_end = if month_end < end_date { month_end } else { end_date };
        let days = (segment_end - current).num_days() + 1;
        total += money(
            balance * monthly_rate * Decimal::from(days) / Decimal::from(days_in_month)
        );
        current = segment_end + Duration::days(1);
    }
    Ok(money(total))
}

fn daily_accrual_reducing(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate_percent = decimal(&req.rate_percent)?;
    let annual_rate = rate_percent / Decimal::from(100_i64);
    let fee = money(decimal(&req.processing_fee)?);
    let start_raw = req.interest_start_date.as_deref()
        .ok_or_else(|| "interest_start_date_required".to_string())?;
    let start_date = parse_date(start_raw)?;
    let due_dates: Vec<NaiveDate> = req.due_dates.iter()
        .map(|value| parse_date(value))
        .collect::<Result<Vec<_>, _>>()?;

    let mut factors = Vec::with_capacity(req.term_months);
    let mut period_start = start_date;
    for due_date in &due_dates {
        factors.push(daily_period_factor(annual_rate, period_start, *due_date)?);
        period_start = *due_date;
    }

    let base_payment = if annual_rate.is_zero() {
        money(principal / Decimal::from(req.term_months as i64))
    } else {
        let mut cumulative = Decimal::ONE;
        let mut discount_sum = Decimal::ZERO;
        for factor in factors {
            cumulative *= Decimal::ONE + factor;
            discount_sum += Decimal::ONE / cumulative;
        }
        if discount_sum.is_zero() {
            return Err("invalid_daily_discount_sum".to_string());
        }
        money(principal / discount_sum)
    };

    let fee_parts = split_amount(fee, req.term_months);
    let mut opening = principal;
    let mut previous_date = start_date;
    let mut total_interest = Decimal::ZERO;
    let mut schedule = Vec::with_capacity(req.term_months);

    for (index, due_date) in due_dates.iter().enumerate() {
        let interest_due =
            daily_segment_interest(opening, annual_rate, previous_date, *due_date)?;
        let principal_due = if index + 1 == req.term_months {
            opening
        } else {
            let candidate = money(base_payment - interest_due);
            let non_negative = if candidate < Decimal::ZERO {
                Decimal::ZERO
            } else {
                candidate
            };
            if non_negative > opening { opening } else { non_negative }
        };
        let closing_candidate = money(opening - principal_due);
        let closing = if closing_candidate < Decimal::ZERO {
            Decimal::ZERO
        } else {
            closing_candidate
        };
        let total_due = money(principal_due + interest_due + fee_parts[index]);
        total_interest += interest_due;
        schedule.push(total_due);
        opening = closing;
        previous_date = *due_date;
    }

    let total_interest = money(total_interest);
    let total = money(schedule.iter().copied().sum::<Decimal>());
    Ok(LoanPreviewResponse {
        method: req.method.clone(),
        monthly_installment: schedule.first().copied().unwrap_or(Decimal::ZERO).to_string(),
        total_interest: total_interest.to_string(),
        total_repayable: total.to_string(),
        schedule_amounts: schedule.into_iter().map(|value| value.to_string()).collect(),
        authoritative: false,
        native_cpp_used: false,
    })
}

fn compound(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate_percent = decimal(&req.rate_percent)?;
    let fee = money(decimal(&req.processing_fee)?);
    let monthly_rate = (rate_percent / Decimal::from(100_i64)) / Decimal::from(12_i64);

    let mut notional = principal;
    let mut rounded_interest: Vec<Decimal> = Vec::with_capacity(req.term_months);
    for _ in 0..req.term_months {
        let interest = money(notional * monthly_rate);
        rounded_interest.push(interest);
        notional = money(notional + interest);
    }

    let mut exact_growth = Decimal::ONE;
    for _ in 0..req.term_months {
        exact_growth *= Decimal::ONE + monthly_rate;
    }
    let exact_total_interest = money(principal * (exact_growth - Decimal::ONE));
    if !rounded_interest.is_empty() {
        let prior = rounded_interest[..rounded_interest.len() - 1]
            .iter()
            .copied()
            .sum::<Decimal>();
        let last = rounded_interest.len() - 1;
        rounded_interest[last] = money(exact_total_interest - prior);
    }

    let principal_parts = split_amount(principal, req.term_months);
    let fee_parts = split_amount(fee, req.term_months);
    let schedule: Vec<Decimal> = (0..req.term_months)
        .map(|i| money(principal_parts[i] + rounded_interest[i] + fee_parts[i]))
        .collect();
    let total = money(schedule.iter().copied().sum::<Decimal>());

    Ok(LoanPreviewResponse {
        method: req.method.clone(),
        monthly_installment: schedule.first().copied().unwrap_or(Decimal::ZERO).to_string(),
        total_interest: exact_total_interest.to_string(),
        total_repayable: total.to_string(),
        schedule_amounts: schedule.into_iter().map(|v| v.to_string()).collect(),
        authoritative: false,
        native_cpp_used: false,
    })
}


#[derive(Debug, Deserialize)]
struct PortfolioRiskRow {
    outstanding_balance: String,
    days_past_due: i64,
    is_written_off: bool,
    branch_label: Option<String>,
    product_label: Option<String>,
    employer_label: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PortfolioRiskRequest {
    rows: Vec<PortfolioRiskRow>,
}

#[derive(Debug, Serialize)]
struct RiskGroupSummary {
    label: String,
    loan_count: usize,
    exposure: String,
    share_percent: String,
    par_30: String,
}

#[derive(Debug, Serialize)]
struct RiskConcentrationSummary {
    hhi: String,
    top_share_percent: String,
    group_count: usize,
    groups: Vec<RiskGroupSummary>,
}

#[derive(Debug, Serialize)]
struct PortfolioRiskResponse {
    active_exposure: String,
    active_loans: usize,
    par_1_amount: String,
    par_1: String,
    par_7_amount: String,
    par_7: String,
    par_30_amount: String,
    par_30: String,
    par_60_amount: String,
    par_60: String,
    par_90_amount: String,
    par_90: String,
    branch: RiskConcentrationSummary,
    product: RiskConcentrationSummary,
    employer: RiskConcentrationSummary,
    authoritative: bool,
}

fn percent(numerator: Decimal, denominator: Decimal) -> Decimal {
    if denominator.is_zero() {
        Decimal::ZERO
    } else {
        (numerator / denominator * Decimal::from(100_i64))
            .round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero)
    }
}

fn concentration(
    rows: &[PortfolioRiskRow],
    selector: fn(&PortfolioRiskRow) -> Option<&String>,
    total: Decimal,
) -> Result<RiskConcentrationSummary, String> {
    use std::collections::BTreeMap;
    let mut grouped: BTreeMap<String, (usize, Decimal, Decimal)> = BTreeMap::new();
    for row in rows.iter().filter(|row| !row.is_written_off) {
        let balance = money(decimal(&row.outstanding_balance)?);
        let label = selector(row).cloned().unwrap_or_else(|| "Unknown".to_string());
        let entry = grouped.entry(label).or_insert((0, Decimal::ZERO, Decimal::ZERO));
        entry.0 += 1;
        entry.1 += balance;
        if row.days_past_due >= 30 {
            entry.2 += balance;
        }
    }

    let mut groups: Vec<RiskGroupSummary> = grouped
        .into_iter()
        .map(|(label, (loan_count, exposure, par30_amount))| {
            let exposure = money(exposure);
            RiskGroupSummary {
                label,
                loan_count,
                exposure: exposure.to_string(),
                share_percent: percent(exposure, total).to_string(),
                par_30: percent(par30_amount, exposure).to_string(),
            }
        })
        .collect();

    groups.sort_by(|a, b| {
        let left = decimal(&a.exposure).unwrap_or(Decimal::ZERO);
        let right = decimal(&b.exposure).unwrap_or(Decimal::ZERO);
        right.cmp(&left).then_with(|| a.label.cmp(&b.label))
    });

    let hhi = groups.iter().fold(Decimal::ZERO, |acc, group| {
        let share = decimal(&group.share_percent).unwrap_or(Decimal::ZERO) / Decimal::from(100_i64);
        acc + share * share
    }) * Decimal::from(10_000_i64);

    Ok(RiskConcentrationSummary {
        hhi: hhi.round_dp_with_strategy(2, RoundingStrategy::MidpointAwayFromZero).to_string(),
        top_share_percent: groups
            .first()
            .map(|group| group.share_percent.clone())
            .unwrap_or_else(|| "0".to_string()),
        group_count: groups.len(),
        groups,
    })
}

fn portfolio_risk_summary(req: &PortfolioRiskRequest) -> Result<PortfolioRiskResponse, String> {
    let active: Vec<&PortfolioRiskRow> = req.rows.iter().filter(|row| !row.is_written_off).collect();
    let exposure = money(active.iter().try_fold(Decimal::ZERO, |acc, row| {
        Ok::<Decimal, String>(acc + money(decimal(&row.outstanding_balance)?))
    })?);

    fn par_amount(rows: &[&PortfolioRiskRow], threshold: i64) -> Result<Decimal, String> {
        Ok(money(rows.iter().try_fold(Decimal::ZERO, |acc, row| {
            if row.days_past_due >= threshold {
                Ok::<Decimal, String>(acc + money(decimal(&row.outstanding_balance)?))
            } else {
                Ok::<Decimal, String>(acc)
            }
        })?))
    }

    let par1 = par_amount(&active, 1)?;
    let par7 = par_amount(&active, 7)?;
    let par30 = par_amount(&active, 30)?;
    let par60 = par_amount(&active, 60)?;
    let par90 = par_amount(&active, 90)?;

    Ok(PortfolioRiskResponse {
        active_exposure: exposure.to_string(),
        active_loans: active.len(),
        par_1_amount: par1.to_string(),
        par_1: percent(par1, exposure).to_string(),
        par_7_amount: par7.to_string(),
        par_7: percent(par7, exposure).to_string(),
        par_30_amount: par30.to_string(),
        par_30: percent(par30, exposure).to_string(),
        par_60_amount: par60.to_string(),
        par_60: percent(par60, exposure).to_string(),
        par_90_amount: par90.to_string(),
        par_90: percent(par90, exposure).to_string(),
        branch: concentration(&req.rows, |row| row.branch_label.as_ref(), exposure)?,
        product: concentration(&req.rows, |row| row.product_label.as_ref(), exposure)?,
        employer: concentration(&req.rows, |row| row.employer_label.as_ref(), exposure)?,
        authoritative: false,
    })
}

fn calculate(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    if req.term_months == 0 || req.term_months > 120 || req.due_dates.len() != req.term_months {
        return Err("invalid term or due_dates".to_string());
    }
    match req.method.as_str() {
        "micro_loan" => micro_loan(req),
        "simple_interest" | "flat_rate" => simple_or_flat(req),
        "compound_interest" => compound(req),
        "reducing_balance" => reducing_balance(req),
        "daily_accrual_reducing" => daily_accrual_reducing(req),
        _ => Err("unsupported_method".to_string()),
    }
}

fn json_response(status: u16, body: String) -> Response<std::io::Cursor<Vec<u8>>> {
    let header = Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap();
    Response::from_string(body)
        .with_status_code(StatusCode(status))
        .with_header(header)
}

fn main() {
    let addr = env::var("LOANHUB_RUST_COMPUTE_ADDR").unwrap_or_else(|_| "0.0.0.0:8082".to_string());
    let server = Server::http(&addr).expect("bind rust compute worker");
    eprintln!("LoanHub Rust compute worker listening on {addr}");

    for mut request in server.incoming_requests() {
        let url = request.url().to_string();

        if request.method() == &Method::Get && url == "/health/ready" {
            let _ = request.respond(json_response(200, r#"{"status":"ready","runtime":"rust"}"#.to_string()));
            continue;
        }

        if request.method() == &Method::Post && url == "/v1/portfolio-risk-summary" {
            let mut body = String::new();
            if request.as_reader().read_to_string(&mut body).is_err() {
                let _ = request.respond(json_response(400, r#"{"error":"invalid_body"}"#.to_string()));
                continue;
            }
            match serde_json::from_str::<PortfolioRiskRequest>(&body)
                .map_err(|_| "invalid_json".to_string())
                .and_then(|payload| portfolio_risk_summary(&payload))
            {
                Ok(result) => {
                    let body = serde_json::to_string(&result).unwrap();
                    let _ = request.respond(json_response(200, body));
                }
                Err(error) => {
                    let body = serde_json::json!({"error": error}).to_string();
                    let _ = request.respond(json_response(422, body));
                }
            }
            continue;
        }

        if request.method() == &Method::Post && url == "/v1/loan-preview" {
            let mut body = String::new();
            let read_result = request.as_reader().read_to_string(&mut body);
            if read_result.is_err() {
                let _ = request.respond(json_response(400, r#"{"error":"invalid_body"}"#.to_string()));
                continue;
            }
            match serde_json::from_str::<LoanPreviewRequest>(&body)
                .map_err(|_| "invalid_json".to_string())
                .and_then(|payload| calculate(&payload))
            {
                Ok(result) => {
                    let body = serde_json::to_string(&result).unwrap();
                    let _ = request.respond(json_response(200, body));
                }
                Err(error) => {
                    let body = serde_json::json!({"error": error}).to_string();
                    let _ = request.respond(json_response(422, body));
                }
            }
            continue;
        }

        if request.method() == &Method::Get && url.starts_with("/v1/variance-classification") {
            let query = url.split_once('?').map(|(_, q)| q).unwrap_or("");
            let mut expected = None;
            let mut actual = None;
            for pair in query.split('&') {
                if let Some((key, value)) = pair.split_once('=') {
                    if key == "expected_cents" { expected = value.parse::<i64>().ok(); }
                    if key == "actual_cents" { actual = value.parse::<i64>().ok(); }
                }
            }
            if let (Some(expected), Some(actual)) = (expected, actual) {
                let variance = actual.saturating_sub(expected);
                let status = if variance == 0 { "matched" } else if variance < 0 { "shortage" } else { "excess" };
                let body = serde_json::json!({
                    "status": status,
                    "variance_cents": variance,
                    "authoritative": false
                }).to_string();
                let _ = request.respond(json_response(200, body));
            } else {
                let _ = request.respond(json_response(400, r#"{"error":"invalid_query"}"#.to_string()));
            }
            continue;
        }

        if request.method() == &Method::Get && url.starts_with("/v1/affordability-headroom") {
            let query = url.split_once('?').map(|(_, q)| q).unwrap_or("");
            let mut income = None;
            let mut commitments = None;
            let mut proposed = None;
            for pair in query.split('&') {
                if let Some((key, value)) = pair.split_once('=') {
                    if key == "income_cents" { income = value.parse::<i64>().ok(); }
                    if key == "commitments_cents" { commitments = value.parse::<i64>().ok(); }
                    if key == "proposed_cents" { proposed = value.parse::<i64>().ok(); }
                }
            }
            if let (Some(income), Some(commitments), Some(proposed)) = (income, commitments, proposed) {
                let headroom = income.saturating_sub(commitments).saturating_sub(proposed);
                let body = serde_json::json!({
                    "passed": headroom >= 0,
                    "headroom_cents": headroom,
                    "authoritative": false
                }).to_string();
                let _ = request.respond(json_response(200, body));
            } else {
                let _ = request.respond(json_response(400, r#"{"error":"invalid_query"}"#.to_string()));
            }
            continue;
        }

        let _ = request.respond(json_response(404, r#"{"error":"not_found"}"#.to_string()));
    }
}
