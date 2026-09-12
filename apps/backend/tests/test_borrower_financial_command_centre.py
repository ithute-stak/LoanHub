from pathlib import Path

import pytest
from pydantic import ValidationError

from database.schemas.borrower_command import (
    BORROWER_SERVICE_REQUEST_TYPES,
    BorrowerConsentUpdate,
    BorrowerServiceRequestCreate,
)


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "backend" / "routers" / "borrower_financial_command.py"
API_ROUTER = ROOT / "backend" / "api" / "v1" / "router.py"
MODEL = ROOT / "backend" / "database" / "models" / "borrower_service_request.py"
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "e4t8v0x2y354_borrower_service_requests.py"
CLIENT_API = ROOT / "frontend" / "api" / "borrowerCommand.ts"
CENTRE = ROOT / "frontend" / "components" / "borrower" / "borrower-financial-centre.tsx"
COMPANY_QUEUE = ROOT / "frontend" / "components" / "borrower" / "company-borrower-request-queue.tsx"
DASHBOARD = ROOT / "frontend" / "app" / "(dashboard)" / "borrower" / "page.tsx"


def test_borrower_service_request_schema_supports_governed_request_types():
    expected = {
        "settlement_quote",
        "payment_arrangement",
        "change_payment_date",
        "top_up",
        "refinance",
        "consolidation",
        "early_repayment",
        "payment_allocation_dispute",
        "balance_dispute",
        "hardship",
        "paid_up_letter",
        "statement",
        "update_payment_account",
    }
    assert BORROWER_SERVICE_REQUEST_TYPES == expected
    payload = BorrowerServiceRequestCreate(request_type=" Settlement_Quote ")
    assert payload.request_type == "settlement_quote"
    with pytest.raises(ValidationError):
        BorrowerServiceRequestCreate(request_type="delete_loan")


def test_borrower_consent_update_is_partial_and_explicit():
    payload = BorrowerConsentUpdate(consent_to_credit_checks=False)
    assert payload.model_dump(exclude_unset=True) == {"consent_to_credit_checks": False}


def test_command_router_exposes_full_borrower_control_surface():
    source = ROUTER.read_text(encoding="utf-8")
    for route in (
        '"/overview"',
        '"/financial-profile"',
        '"/consents"',
        '"/applications"',
        '"/offers/{request_id}"',
        '"/repayment-calendar"',
        '"/payoff/{loan_id}"',
        '"/eligibility"',
        '"/timeline"',
        '"/security"',
        '"/service-requests"',
        '"/company/service-requests"',
    ):
        assert route in source
    assert "calculate_loan_terms(" in source
    assert "not a credit-bureau score" in source
    assert "not an approval, offer or promise of credit" in source
    assert "official settlement quotation" in source
    assert "MarketplaceUnlock.status == UnlockStatus.UNLOCKED" in source


def test_service_requests_are_persistent_tenant_scoped_workflows():
    model_source = MODEL.read_text(encoding="utf-8")
    migration_source = MIGRATION.read_text(encoding="utf-8")
    assert '__tablename__ = "borrower_service_requests"' in model_source
    assert 'ForeignKey("borrowers.id", ondelete="CASCADE")' in model_source
    assert 'ForeignKey("loan_companies.id", ondelete="CASCADE")' in model_source
    assert 'ForeignKey("client_company_loan.id", ondelete="SET NULL")' in model_source
    assert 'revision: str = "e4t8v0x2y354"' in migration_source
    assert 'down_revision: Union[str, Sequence[str], None] = "d3s7u9w1x243"' in migration_source
    assert '"borrower_service_requests"' in migration_source


def test_api_registry_mounts_command_router_once():
    source = API_ROUTER.read_text(encoding="utf-8")
    assert "borrower_financial_command," in source
    assert source.count("borrower_financial_command.router") == 1


def test_frontend_has_command_centre_lender_queue_and_safety_copy():
    client_source = CLIENT_API.read_text(encoding="utf-8")
    centre_source = CENTRE.read_text(encoding="utf-8")
    queue_source = COMPANY_QUEUE.read_text(encoding="utf-8")
    dashboard_source = DASHBOARD.read_text(encoding="utf-8")

    assert '"/borrower-command/overview"' in client_source
    assert '"/borrower-command/eligibility"' in client_source
    assert '"/borrower-command/company/service-requests"' in client_source
    assert "Borrower Financial Command Centre" in centre_source
    assert "LoanHub readiness" in centre_source
    assert "Request official settlement" in centre_source
    assert "Product eligibility guide" in centre_source
    assert "Who accessed marketplace profile data" in centre_source
    assert "Borrower service-request queue" in queue_source
    assert 'href="/borrower/financial-centre"' in dashboard_source
