//! Advisory C++ accounting computation. Rust recomputes and accepts exact parity only.
//! No journal posting or database mutations occur here.
use std::collections::BTreeMap;
use super::cpp_execute;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JournalLine {
    pub account_id: i64,
    pub debit_cents: i64,
    pub credit_cents: i64,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AccountTotal {
    pub account_id: i64,
    pub debit_cents: i64,
    pub credit_cents: i64,
    pub net_debit_cents: i64,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TrialBalance {
    pub debit_cents: i64,
    pub credit_cents: i64,
    pub accounts: Vec<AccountTotal>,
}
pub struct AdvisoryTrialBalance {
    pub result: TrialBalance,
    pub native_cpp_used: bool,
}
fn checked(value: i128) -> Result<i64, &'static str> {
    i64::try_from(value).map_err(|_| "accounting overflow")
}
fn validate_line(row: &JournalLine) -> Result<(), &'static str> {
    if row.account_id <= 0 || row.debit_cents < 0 || row.credit_cents < 0
        || (row.debit_cents == 0 && row.credit_cents == 0)
        || (row.debit_cents != 0 && row.credit_cents != 0) {
        return Err("invalid journal line");
    }
    Ok(())
}
pub fn validate_journal(rows: &[JournalLine]) -> Result<(), &'static str> {
    if rows.len() < 2 { return Err("journal requires two or more lines"); }
    let mut debit = 0_i128;
    let mut credit = 0_i128;
    for row in rows {
        validate_line(row)?;
        debit += i128::from(row.debit_cents);
        credit += i128::from(row.credit_cents);
    }
    checked(debit)?;
    checked(credit)?;
    if debit != credit { return Err("unbalanced journal"); }
    Ok(())
}
pub fn trial_balance(rows: &[JournalLine]) -> Result<TrialBalance, &'static str> {
    let mut by_account = BTreeMap::<i64, (i128, i128)>::new();
    let mut debits = 0_i128;
    let mut credits = 0_i128;
    for row in rows {
        validate_line(row)?;
        let totals = by_account.entry(row.account_id).or_default();
        totals.0 += i128::from(row.debit_cents);
        totals.1 += i128::from(row.credit_cents);
        debits += i128::from(row.debit_cents);
        credits += i128::from(row.credit_cents);
    }
    let mut accounts = Vec::with_capacity(by_account.len());
    for (account_id, (debit, credit)) in by_account {
        accounts.push(AccountTotal {
            account_id,
            debit_cents: checked(debit)?,
            credit_cents: checked(credit)?,
            net_debit_cents: checked(debit - credit)?,
        });
    }
    Ok(TrialBalance {
        debit_cents: checked(debits)?,
        credit_cents: checked(credits)?,
        accounts,
    })
}
fn payload(rows: &[JournalLine]) -> String {
    rows.iter().map(|r| format!("{}|{}|{}\n", r.account_id, r.debit_cents, r.credit_cents)).collect()
}
fn parse_cpp_balance(raw: &str) -> Option<TrialBalance> {
    let mut lines = raw.lines();
    let header = lines.next()?;
    let parts: Vec<&str> = header.split('|').collect();
    if parts.len() != 2 { return None; }
    let debit_cents = parts[0].parse().ok()?;
    let credit_cents = parts[1].parse().ok()?;
    let mut accounts = Vec::new();
    for line in lines {
        let p: Vec<&str> = line.split('|').collect();
        if p.len() != 4 { return None; }
        accounts.push(AccountTotal {
            account_id: p[0].parse().ok()?,
            debit_cents: p[1].parse().ok()?,
            credit_cents: p[2].parse().ok()?,
            net_debit_cents: p[3].parse().ok()?,
        });
    }
    Some(TrialBalance { debit_cents, credit_cents, accounts })
}
pub fn advisory_trial_balance(rows: &[JournalLine]) -> Result<AdvisoryTrialBalance, &'static str> {
    let rust_result = trial_balance(rows)?;
    let cpp_result = cpp_execute("accounting-trial-balance", &payload(rows))
        .and_then(|raw| parse_cpp_balance(&raw));
    let native_cpp_used = cpp_result.as_ref() == Some(&rust_result);
    Ok(AdvisoryTrialBalance {
        result: if native_cpp_used { cpp_result.unwrap() } else { rust_result },
        native_cpp_used,
    })
}
pub fn advisory_validate_journal(rows: &[JournalLine]) -> Result<bool, &'static str> {
    validate_journal(rows)?;
    Ok(cpp_execute("accounting-journal-validate", &payload(rows))
        .as_deref() == Some("balanced\n"))
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn journal_and_trial_balance() {
        let rows = vec![
            JournalLine { account_id: 20, debit_cents: 0, credit_cents: 300 },
            JournalLine { account_id: 10, debit_cents: 300, credit_cents: 0 },
        ];
        validate_journal(&rows).unwrap();
        let tb = trial_balance(&rows).unwrap();
        assert_eq!((tb.debit_cents, tb.credit_cents), (300, 300));
        assert_eq!(tb.accounts[0].account_id, 10);
        assert_eq!(tb.accounts[1].net_debit_cents, -300);
        let advisory = advisory_trial_balance(&rows).unwrap();
        assert_eq!(advisory.result, tb);
    }
    #[test]
    fn rejects_invalid_and_overflow() {
        assert!(validate_journal(&[]).is_err());
        assert!(validate_journal(&[
            JournalLine { account_id: 10, debit_cents: 100, credit_cents: 0 },
            JournalLine { account_id: 20, debit_cents: 0, credit_cents: 99 },
        ]).is_err());
        assert!(trial_balance(&[
            JournalLine { account_id: 10, debit_cents: i64::MAX, credit_cents: 0 },
            JournalLine { account_id: 10, debit_cents: 1, credit_cents: 0 },
        ]).is_err());
    }
}
