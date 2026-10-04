use rust_decimal::prelude::*;
use rust_decimal::RoundingStrategy;
use serde::{Deserialize, Serialize};
use std::env;
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
    })
}

fn simple_or_flat(req: &LoanPreviewRequest) -> Result<LoanPreviewResponse, String> {
    let principal = money(decimal(&req.principal)?);
    let rate_percent = decimal(&req.rate_percent)?;
    let fee = money(decimal(&req.processing_fee)?);
    let annual_rate = rate_percent / Decimal::from(100_i64);
    let total_interest = money(
        principal * annual_rate * Decimal::from(req.term_months as i64) / Decimal::from(12_i64),
    );
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
