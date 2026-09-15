from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_handoff_router_is_company_scoped_and_uses_normal_origination_policy() -> None:
    router = _read(BACKEND / "routers" / "cdas_application_handoff.py")

    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "DirectLoanApplication.company_id == context.company_id" in router
    assert "CompanyBorrowerAccount.company_id == context.company_id" in router
    assert 'CompanyBorrowerAccount.status == "active"' in router
    assert "require_tenant_roles(context, LENDING_ROLES)" in router
    assert "assert_branch_scope(context" in router
    assert "get_or_create_policy" in router
    assert "enforce_duplicate_policy" in router
    assert "LoanProduct.company_id == context.company_id" in router
    assert "LoanProduct.is_active.is_(True)" in router


def test_handoff_creates_only_a_draft_from_staff_entered_credit_fields() -> None:
    router = _read(BACKEND / "routers" / "cdas_application_handoff.py")

    for required in (
        "borrower_id: UUID",
        "requested_amount: Decimal",
        "term_count: int",
        "installment_due_dates: list[date]",
    ):
        assert required in router

    assert 'channel="cdas_booking"' in router
    assert 'application_type="new_loan"' in router
    assert 'status="draft"' in router
    assert "requested_amount=Decimal(payload.requested_amount)" in router
    assert "term_count=payload.term_count" in router
    assert "installment_due_dates=[value.isoformat() for value in payload.installment_due_dates]" in router

    # CDAS-derived financial/capacity values must never become an origination
    # amount, term, price, affordability result or approval decision.
    for banned in (
        "assessed_available_amount",
        "available_capacity",
        "amount_owing",
        "booking_months",
        "approved_amount=",
        "interest_rate=",
        "affordability_snapshot=",
        "affordability_assessment_id=",
    ):
        assert banned not in router


def test_handoff_provenance_is_exact_conservative_and_idempotent() -> None:
    router = _read(BACKEND / "routers" / "cdas_application_handoff.py")
    model = _read(BACKEND / "database" / "models" / "professional_lending.py")
    migration = _read(BACKEND / "alembic" / "versions" / "g7v1w3x5y030_cdas_application_handoff.py")

    assert "CdasAnalysisRecord.client_reference == reference" in router
    assert "CdasAnalysisRecord.nid == nid" in router
    assert "CdasAnalysisRecord.employee_no == employee_no" in router
    assert "client_name ==" not in router
    assert "cdas_source_opportunity_id == opportunity.id" in router
    assert "status_code=409" in router

    for field in (
        "cdas_source_opportunity_id",
        "cdas_source_analysis_id",
        "cdas_handoff_by_user_id",
        "cdas_handoff_at",
    ):
        assert field in model
        assert field in migration

    assert 'unique=True' in model
    assert '"uq_direct_loan_applications_cdas_source_opportunity"' in migration
    assert 'down_revision = "f6u0v2w4x029"' in migration


def test_handoff_frontend_is_wired_to_existing_origination_workspace() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    types = _read(FRONTEND / "types" / "cdasApplicationHandoff.ts")
    page = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "applications"
        / "page.tsx"
    )
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    registry = _read(BACKEND / "api" / "v1" / "router.py")

    assert '"/cdas-booking/application-handoffs"' in api
    assert "/application-handoff`" in api
    assert 'href="/company/cdas-booking/applications"' in layout
    assert "LoanHub Applications" in layout
    assert "cdas_application_handoff" in registry
    assert "cdas_application_handoff.router" in registry

    for expected in (
        "borrower_id",
        "requested_amount",
        "term_count",
        "installment_due_dates",
        "origination_workspace_url",
    ):
        assert expected in types

    for phrase in (
        "CDAS → LoanHub Applications",
        "CDAS context is not a credit decision",
        "The officer must choose the LoanHub client and enter the requested loan details manually",
        "Create draft & continue",
        "Continue application",
    ):
        assert phrase in page
    assert "router.push(result.origination_workspace_url)" in page
    assert "/company/origination/new?application=" in page


def test_handoff_contract_does_not_auto_match_a_borrower_or_credit_terms() -> None:
    page = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "applications"
        / "page.tsx"
    )
    router = _read(BACKEND / "routers" / "cdas_application_handoff.py")

    assert 'setBorrowerId("")' in page
    assert "Select the verified company client" in page
    assert "Enter the client's requested amount" in page
    assert "Enter every date explicitly" in page
    assert "Draft only. CDAS did not determine amount, term, affordability, pricing, approval or disbursement." in router
