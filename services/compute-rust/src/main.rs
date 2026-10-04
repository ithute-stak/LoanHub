use std::io::{self, BufRead};

fn cents(value: &str) -> i64 {
    let value = value.trim();
    let negative = value.starts_with('-');
    let raw = value.trim_start_matches('-');
    let mut parts = raw.splitn(2, '.');
    let whole: i64 = parts.next().unwrap_or("0").parse().unwrap_or(0);
    let frac_raw = parts.next().unwrap_or("0");
    let mut frac = frac_raw.chars().take(2).collect::<String>();
    while frac.len() < 2 { frac.push('0'); }
    let frac: i64 = frac.parse().unwrap_or(0);
    let result = whole.saturating_mul(100).saturating_add(frac);
    if negative { -result } else { result }
}

fn main() {
    // Deliberately tiny first contract:
    // stdin line: affordability|income|commitments|proposed_installment
    // stdout: pass|headroom_cents
    //
    // Python remains authoritative. This worker is suitable for high-volume
    // previews/batch analytics and must not directly approve a loan.
    for line in io::stdin().lock().lines().map_while(Result::ok) {
        let fields: Vec<&str> = line.split('|').collect();
        if fields.len() != 4 || fields[0] != "affordability" {
            println!("error|unsupported_contract");
            continue;
        }
        let income = cents(fields[1]);
        let commitments = cents(fields[2]);
        let proposed = cents(fields[3]);
        let headroom = income.saturating_sub(commitments).saturating_sub(proposed);
        println!("{}|{}", if headroom >= 0 { "pass" } else { "fail" }, headroom);
    }
}
