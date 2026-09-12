from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from database.schemas.company_clients import CompanyClientExternalDebtInput
from database.schemas.origination import DebtObligationInput


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"


def debt_payload(**overrides):
    payload = {
        "creditor": "Existing lender",
        "started_on": date.today() - timedelta(days=180),
        "original_amount": "12000.00",
        "current_balance": "6000.00",
        "installment_amount": "750.00",
        "installment_frequency": "monthly",
        "total_installments": 16,
        "installments_paid": 8,
        "remaining_installments": 8,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_external_debt_schema_requires_a_trackable_active_schedule() -> None:
    row = CompanyClientExternalDebtInput(**debt_payload(remaining_installments=None))
    assert row.remaining_installments == 8

    with pytest.raises(ValidationError, match="installment amount"):
        CompanyClientExternalDebtInput(**debt_payload(installment_amount="0"))

    with pytest.raises(ValidationError, match="start date"):
        CompanyClientExternalDebtInput(
            **debt_payload(started_on=date.today() + timedelta(days=1))
        )


def test_origination_schema_preserves_identity_and_remaining_installments() -> None:
    row = DebtObligationInput(
        id=None,
        account_reference=None,
        debt_type="microloan",
        monthly_installment="750.00",
        settlement_amount=None,
        remaining_term_months=8,
        source="declared",
        is_verified=False,
        notes=None,
        next_due_date=None,
        **debt_payload(),
    )
    assert row.remaining_installments == 8
    assert row.installment_amount == row.monthly_installment


def test_migration_adds_schedule_columns_and_event_history() -> None:
    migration = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "a0p4r6s8t910_external_debt_tracking.py"
    ).read_text()
    assert 'revision: str = "a0p4r6s8t910"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"' in migration
    for column in (
        "started_on",
        "installment_amount",
        "installment_frequency",
        "total_installments",
        "installments_paid",
        "remaining_installments",
        "next_due_date",
        "status",
    ):
        assert f'Column("{column}"' in migration
    assert '"borrower_debt_obligation_events"' in migration
    explicit_names = [
        "ix_bdo_status",
        "ix_bdo_reviewer",
        "fk_bdo_reviewer_user",
        "ix_bdoe_company",
        "ix_bdoe_borrower",
        "ix_bdoe_obligation",
        "ix_bdoe_recorder",
        "ix_bdoe_type",
    ]
    assert all(len(name.encode()) <= 63 for name in explicit_names)


def test_backend_persists_assisted_debts_and_reuses_monthly_commitments() -> None:
    service = (BACKEND_ROOT / "services" / "company_client_service.py").read_text()
    origination = (BACKEND_ROOT / "services" / "origination_service.py").read_text()
    router = (BACKEND_ROOT / "routers" / "company_clients.py").read_text()

    assert "def save_assisted_external_debts" in service
    assert "external_debt_monthly_commitment" in service
    assert "BorrowerDebtObligationEvent(" in service
    assert "normalized_monthly_debt_installment" in service
    assert "BorrowerDebtObligation.status.in_" in origination
    assert "func.sum(BorrowerDebtObligation.monthly_installment)" in origination
    assert '"/{account_id}/external-debts/{debt_id}/payments"' in router
    assert "remaining_installments_after" in router


def test_origination_updates_tracked_rows_instead_of_recreating_all_debts() -> None:
    service = (BACKEND_ROOT / "services" / "origination_service.py").read_text()
    assert 'item.model_dump(exclude={"id"})' in service
    assert "BorrowerDebtObligation.id == item.id" in service
    assert "One of the tracked external loans was not found" in service
    assert "BorrowerDebtObligationEvent(" in service

    debt_section = service[
        service.index("debt_rows = []") : service.index("existing_banks = (")
    ]
    assert "db.query(BorrowerDebtObligation)" in debt_section
    assert ".delete(" not in debt_section


def test_registration_ui_captures_start_date_installments_and_remaining_schedule() -> None:
    page = (
        FRONTEND_ROOT
        / "app"
        / "(dashboard)"
        / "company"
        / "clients"
        / "page.tsx"
    ).read_text()
    fields = (
        FRONTEND_ROOT
        / "components"
        / "clients"
        / "external-debt-registration-fields.tsx"
    ).read_text()

    assert "ExternalDebtRegistrationFields" in page
    assert "external_debts: normalizedDebts" in page
    assert "External monthly commitment" in page
    assert 'label="Loan started"' in fields
    assert 'label="Installment amount"' in fields
    assert 'label="Installments remaining"' in fields
    assert 'label="Next due date"' in fields


def test_profile_has_a_payment_and_history_tracker_for_external_loans() -> None:
    dialog = (
        FRONTEND_ROOT
        / "components"
        / "clients"
        / "company-client-profile-dialog.tsx"
    ).read_text()
    tracker = (
        FRONTEND_ROOT
        / "components"
        / "clients"
        / "external-debt-tracker.tsx"
    ).read_text()
    editor = (
        FRONTEND_ROOT
        / "components"
        / "clients"
        / "company-client-profile-editor-cards.tsx"
    ).read_text()

    assert "ExternalDebtTracker" in dialog
    assert "Record external loan payment" in tracker
    assert "Tracking history" in tracker
    assert "installments remaining" in tracker
    assert "Use Payments & loans" in editor
    assert 'label="Existing loan total"' not in editor
