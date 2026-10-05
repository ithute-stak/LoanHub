"""Source-contract coverage for platform-owned Credit Bureau PAYG access."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_company_access_requires_platform_approved_subscription() -> None:
    company_router = _read(ROOT / "routers/credit_bureau_configuration.py")
    enquiry_router = _read(ROOT / "routers/credit_bureau.py")
    service = _read(ROOT / "services/credit_bureau_payg_service.py")

    assert '@router.post("/experian/subscription")' in company_router
    assert "request_subscription(" in company_router
    assert "A lending company cannot enable Experian directly" in company_router
    assert "require_approved_subscription" in enquiry_router
    assert "subscription = require_approved_subscription" in enquiry_router
    assert 'row.status == "pending"' in service
    assert 'row.status != "approved"' in service


def test_platform_owner_controls_subscription_decision_and_tariff() -> None:
    router = _read(ROOT / "routers/platform_credit_bureau.py")
    schema = _read(ROOT / "database/schemas/credit_bureau.py")

    assert '@router.get("/experian/subscriptions")' in router
    assert '@router.post("/experian/subscriptions/{company_id}/decision")' in router
    assert "require_platform_owner" in router
    assert "positive PAYG price" in router
    assert "review_subscription(" in router
    assert 'Literal["approved", "rejected", "suspended"]' in schema


def test_successful_fresh_enquiry_is_charged_once_and_cached_reuse_is_free() -> None:
    router = _read(ROOT / "routers/credit_bureau.py")
    service = _read(ROOT / "services/credit_bureau_payg_service.py")
    model = _read(ROOT / "database/models/platform_credit_bureau.py")

    reuse_block = router.split("if not payload.force_refresh:", 1)[1].split("consent_reference", 1)[0]
    assert "return _enquiry_payload(reusable)" in reuse_block
    assert "accrue_successful_enquiry" not in reuse_block
    assert "accrue_successful_enquiry(" in router
    assert 'UniqueConstraint("enquiry_id", name="uq_credit_bureau_payg_enquiry")' in model
    assert "if existing:" in service
    assert "return existing" in service
    assert '"charge_trigger": "successful_fresh_provider_enquiry"' in service


def test_payg_ledger_is_company_scoped_and_platform_visible() -> None:
    model = _read(ROOT / "database/models/platform_credit_bureau.py")
    company_router = _read(ROOT / "routers/credit_bureau.py")
    platform_router = _read(ROOT / "routers/platform_credit_bureau.py")

    assert '__tablename__ = "platform_credit_bureau_transactions"' in model
    assert 'ForeignKey("loan_companies.id", ondelete="CASCADE")' in model
    assert '@router.get("/experian/transactions")' in company_router
    assert "company_transactions(db, company_id=context.company_id" in company_router
    assert '@router.get("/experian/transactions")' in platform_router
    assert "PlatformCreditBureauTransaction.provider == \"experian\"" in platform_router


def test_frontend_exposes_request_approve_and_payg_price_workflow() -> None:
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")
    platform_page = _read(FRONTEND_ROOT / "app/(dashboard)/superadmin/control/integrations/experian/page.tsx")
    api = _read(FRONTEND_ROOT / "api/creditBureau.ts")

    assert "Credit Bureau PAYG subscription" in company_page
    assert "Request subscription" in company_page
    assert "per successful fresh enquiry" in company_page
    assert "Enable Experian for this company" not in company_page
    assert "Loan company Credit Bureau subscriptions" in platform_page
    assert "Default PAYG price per successful enquiry" in platform_page
    assert "Approve at" in platform_page
    assert "/credit-bureau/experian/subscription" in api
    assert "/platform-owner/credit-bureau/experian/subscriptions" in api


def test_payg_migration_extends_current_alembic_head() -> None:
    migration = _read(ROOT / "alembic/versions/a8c2e4f6g810_credit_bureau_payg.py")

    assert 'revision = "a8c2e4f6g810"' in migration
    assert 'down_revision = "7d2e4f6a8b10"' in migration
    assert '"platform_credit_bureau_subscriptions"' in migration
    assert '"platform_credit_bureau_transactions"' in migration
    assert '"uq_credit_bureau_payg_enquiry"' in migration


def test_only_company_owner_can_switch_experian_environment() -> None:
    router = _read(ROOT / "routers/credit_bureau_configuration.py")
    company_page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")

    assert "context.role != UserRole.COMPANY_OWNER" in router
    assert "Only the Loan Company Owner can switch Credit Bureau between Sandbox and Live." in router
    assert 'const canSwitchEnvironment = activeRole === "company_owner";' in company_page
    assert "Only the Loan Company Owner can switch this mode." in company_page
