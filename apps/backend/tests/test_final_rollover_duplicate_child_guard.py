"""Transfer plans cannot be prepared for a parent with an existing linked loan."""
from pathlib import Path


def test_duplicate_child_guard_is_tenant_scoped_and_blocks_transfer_plan():
    router = (Path(__file__).resolve().parents[3] / "apps/backend/routers/loans.py").read_text()
    section = router.split('def final_rollover_transfer_plan(', 1)[1].split('@router.get("/{loan_id}/installments/{installment_id}/final-rollover-preview")', 1)[0]
    assert "ClientCompanyLoan.parent_loan_id == loan.id" in section
    assert "ClientCompanyLoan.company_id == context.company_id" in section
    assert 'status_code=409' in section
    assert section.index("existing_child") < section.index("prepare_linked_rollover(")
