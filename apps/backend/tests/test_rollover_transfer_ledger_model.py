"""Ensure the proposed rollover ledger has one transfer per parent and child."""
from sqlalchemy import CheckConstraint, UniqueConstraint
from database.models.loan_rollover_transfer import LoanRolloverTransfer


def test_transfer_uniqueness_and_component_accounting_constraints():
    table = LoanRolloverTransfer.__table__
    unique = {
        tuple(col.name for col in c.columns)
        for c in table.constraints if isinstance(c, UniqueConstraint)
    }
    assert ("parent_loan_id",) in unique
    assert ("child_loan_id",) in unique
    assert ("company_id", "transfer_reference") in unique
    check_sql = " ".join(str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint))
    assert "transfer_amount = principal_component + interest_component + fee_component" in check_sql
    assert "parent_loan_id <> child_loan_id" in check_sql
    assert "transfer_amount > 0" in check_sql


def test_ledger_links_to_real_loan_and_original_installment():
    columns = LoanRolloverTransfer.__table__.columns
    for name in ("parent_loan_id", "child_loan_id", "source_installment_id", "approval_reference", "agreement_reference", "posted_by_user_id"):
        assert name in columns
        assert not columns[name].nullable
