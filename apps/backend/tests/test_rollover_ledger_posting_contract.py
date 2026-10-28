"""Ensure proposed financial posting and immutable ledger persist in one unit of work.

Posting is deliberately disabled; these checks protect the implementation
while real PostgreSQL end-to-end tests and accounting review are pending.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = (ROOT / "services/final_installment_rollover_posting.py").read_text()
MODEL = (ROOT / "database/models/loan_rollover_transfer.py").read_text()


def test_loan_and_transfer_record_share_one_commit_boundary():
    assert "db.add(LoanRolloverTransfer(" in SERVICE
    assert SERVICE.index("db.add(child)") < SERVICE.index("db.add(LoanRolloverTransfer(")
    assert SERVICE.index("db.add(LoanRolloverTransfer(") < SERVICE.index("db.flush()\n    if Decimal(str(parent.balance))")
    assert SERVICE.index("db.add(LoanRolloverTransfer(") < SERVICE.index("db.commit()")
    assert SERVICE.count("db.commit()") == 1


def test_source_payment_history_remains_unchanged():
    assert "PaymentTransaction(" not in SERVICE
    assert "PaymentAllocation(" not in SERVICE
    assert "row.paid_amount =" not in SERVICE
    assert 'row.is_superseded = True' in SERVICE


def test_service_stays_disabled_before_db_read():
    function = SERVICE.split("def post_final_rollover(", 1)[1]
    assert function.index("status_code=503") < function.index(".with_for_update()")
    compile(SERVICE, str(ROOT / "services/final_installment_rollover_posting.py"), "exec")


def test_ledger_has_auditable_approval_components():
    for required in ("parent_loan_id", "child_loan_id", "source_installment_id", "transfer_reference",
                     "agreement_reference", "approval_reference", "principal_component",
                     "interest_component", "fee_component", "transfer_amount", "posted_by_user_id"):
        assert required in MODEL
