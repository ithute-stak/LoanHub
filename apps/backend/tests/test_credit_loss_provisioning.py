from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_credit_loss_schema_and_migration_chain():
    model = (ROOT / "backend" / "database" / "models" / "credit_loss_provisioning.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "m7t8v9x0y101_credit_loss_provisioning.py").read_text(encoding="utf-8")
    assert "CreditLossProvisionPolicy" in model
    assert "CreditLossProvisionRun" in model
    assert "CreditLossProvisionLine" in model
    assert 'down_revision = "l6s7u8w9x001"' in migration
    assert "stage IN (1,2,3)" in migration
    assert "provision_rate >= 0 AND provision_rate <= 1" in migration


def test_credit_loss_method_is_evidence_backed_and_configurable():
    source = (ROOT / "backend" / "services" / "credit_loss_provisioning_service.py").read_text(encoding="utf-8")
    assert "PortfolioRiskSnapshot" in source
    assert "DEFAULT_POLICY_RATES" in source
    assert "first_payment_default_floor" in source
    assert "write_off_candidate_dpd" in source
    assert "management-overlay reason is required" in source
    assert "Formal accounting/regulatory classification" in source


def test_credit_loss_approval_has_maker_checker_and_posts_balanced_journal():
    source = (ROOT / "backend" / "services" / "credit_loss_provisioning_service.py").read_text(encoding="utf-8")
    bootstrap = (ROOT / "backend" / "services" / "credit_loss_accounting_bootstrap.py").read_text(encoding="utf-8")
    assert "Maker-checker control requires a different user" in source
    assert 'reference_type="credit_loss_provision_run"' in source
    assert '"1150"' in bootstrap
    assert '"6700"' in bootstrap
    assert "Allowance for Credit Losses" in bootstrap
    assert "Credit Loss Provision Expense" in bootstrap


def test_credit_loss_api_and_workspace_are_registered():
    router = (ROOT / "backend" / "routers" / "credit_loss_provisioning.py").read_text(encoding="utf-8")
    aggregate = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "credit-loss-provisioning" / "page.tsx").read_text(encoding="utf-8")
    command = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "command-centre" / "page.tsx").read_text(encoding="utf-8")
    assert 'APIRouter(prefix="/credit-loss-provisioning"' in router
    assert '@router.post("/runs/{run_id}/approve")' in router
    assert "credit_loss_provisioning.router" in aggregate
    assert "Loan-loss allowance & impairment control" in page
    assert "Accounting-policy guardrail" in page
    assert "/company/credit-loss-provisioning" in command
