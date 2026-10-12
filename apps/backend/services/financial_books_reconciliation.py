"""Read-only checks comparing financial-books trial balance and ledger summaries."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _amount(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid financial amount in report") from exc
    if not result.is_finite():
        raise ValueError("Non-finite financial amount in report")
    return result.quantize(Decimal("0.01"))


def reconcile_books_pack(pack: dict) -> dict:
    """Return explicit inconsistencies, never adjust or mutate accounting figures."""
    trial = pack.get("trial_balance") or {}
    ledger = pack.get("general_ledger") or []
    if not trial.get("lines") or not ledger:
        return {"reconciled": False, "findings": ["missing_trial_balance_or_ledger"]}
    findings: list[str] = []
    debit = sum((_amount(row["debit"]) for row in trial["lines"]), Decimal("0.00"))
    credit = sum((_amount(row["credit"]) for row in trial["lines"]), Decimal("0.00"))
    if debit != credit:
        findings.append("trial_balance_not_balanced")
    if debit != _amount(trial.get("total_debit")) or credit != _amount(trial.get("total_credit")):
        findings.append("trial_balance_header_mismatch")
    if debit - credit != _amount(trial.get("difference")):
        findings.append("trial_balance_difference_mismatch")
    by_account = {}
    for row in ledger:
        account = str(row["account_id"])
        if account in by_account:
            findings.append("duplicate_ledger_account")
        by_account[account] = row
    trial_accounts = {str(row["account_id"]) for row in trial["lines"]}
    if trial_accounts != set(by_account):
        findings.append("ledger_trial_account_mismatch")
    for row in trial["lines"]:
        account = str(row["account_id"])
        ledger_row = by_account.get(account)
        if ledger_row is None:
            continue
        # Debit and credit in the trial balance are net balances. Compare
        # against ledger closing balances using the account's normal side.
        signed = _amount(ledger_row["closing_balance"])
        if ledger_row.get("normal_balance") == "credit":
            signed = -signed
        expected = max(signed, Decimal("0.00"))
        expected_credit = max(-signed, Decimal("0.00"))
        if _amount(row["debit"]) != expected or _amount(row["credit"]) != expected_credit:
            findings.append(f"account_closing_balance_mismatch:{account}")
    return {"reconciled": not findings, "findings": findings}
