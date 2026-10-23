from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def test_new_loan_action_requires_completed_settled_loan_and_active_client():
    source = (FRONTEND / "components/loans/loan-portfolio-workspace.tsx").read_text()
    assert 'loan.status === "completed" && Number(loan.balance) <= 0 && client?.status === "active"' in source
    assert 'request_loan=\u0024{encodeURIComponent(client!.id)}' in source


def test_reloan_action_reuses_existing_loan_request_dialog():
    source = (FRONTEND / "app/(dashboard)/company/clients/page.tsx").read_text()
    assert 'get("request_loan")' in source
    assert 'startInternalLoan(matched)' in source
    assert 'if (matched.status !== "active")' in source
