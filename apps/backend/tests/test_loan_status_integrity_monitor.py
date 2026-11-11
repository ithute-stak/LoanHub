"""Safety and scope checks for LoanHub read-only status integrity audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
AUDIT = ROOT / "scripts" / "audits" / "loan_status_integrity_monitor_readonly.sql"


def test_monitor_is_strictly_read_only() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert "REPEATABLE READ READ ONLY" in text
    assert "ROLLBACK;" in text
    statements = "\n".join(line for line in text.lower().splitlines()
                           if not line.strip().startswith("--"))
    assert not re.search(r"\b(update|delete|insert|truncate|alter|drop|create)\s+", statements)


def test_monitor_does_not_use_national_id_to_match_loans() -> None:
    text = AUDIT.read_text(encoding="utf-8").lower()
    statements = "\n".join(line for line in text.splitlines()
                           if not line.strip().startswith("--"))
    assert "national_id" not in statements
    assert "lc.loan_id=l.id" in statements
    assert "t.parent_loan_id=l.id" in statements
    assert "p.loan_id=f.id" in statements


def test_monitor_preserves_legitimate_settlement_exceptions() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert "topup_parent_settled" in text
    assert "calculated_early_settlement" in text
    assert "legacy_linked" in text
    assert "COMPLETED_UNDERPAID_WITHOUT_SETTLEMENT_EVIDENCE" in text
    assert "COMPLETED_POSITIVE_BALANCE" in text
    assert "OPEN_LOAN_ZERO_BALANCE" in text
