"""Guardrails ensuring the shadow hook stays opt-in and non-posting."""
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def test_reversal_shadow_is_explicitly_opt_in():
    source = (BACKEND / "services" / "loan_last_payment_reversal.py").read_text()
    assert 'os.getenv("LOANHUB_PAYMENT_ENGINE_REVERSAL_SHADOW", "")' in source
    assert 'in {"1", "true", "yes"}' in source
    assert 'inspect_cash_reversal_shadow(' in source
    assert '_logger.exception(' in source


def test_shadow_does_not_write_post_or_commit():
    source = (BACKEND / "payment_engine" / "reversal_shadow.py").read_text()
    forbidden = ("db.commit(", "db.flush(", "db.add(", "db.delete(", "record_reversal_accounting(", "void_treasury_entry(", "reverse_loan_payment(")
    for operation in forbidden:
        assert operation not in source
    assert "preview_cash_reversal(request)" in source
    assert "JournalEntry.status == \"posted\"" in source


def test_shadow_remains_before_authoritative_reversal():
    source = (BACKEND / "services" / "loan_last_payment_reversal.py").read_text()
    workflow = source[source.index("def reverse_latest_cash_repayment("):]
    assert workflow.index("inspect_cash_reversal_shadow(") < workflow.index("reverse_loan_payment(db, payment)")
