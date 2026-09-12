from pathlib import Path

import pytest
from pydantic import ValidationError

from database.schemas.company_clients import (
    CompanyClientNationalIdChangeDecision,
    CompanyClientProfileUpdate,
)
from services.borrower_identity_change_service import normalise_national_id


ROOT = Path(__file__).parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def test_profile_update_schema_allows_editable_sections_but_not_direct_national_id():
    payload = CompanyClientProfileUpdate(
        first_name="Mabasía",
        phone="69024011",
        employment_status="employed",
        bank_account={
            "account_holder": "Mabasía P Ntsebe",
            "bank_name": "Standard Lesotho Bank",
            "account_number": "1234567890",
        },
    )
    assert payload.first_name == "Mabasía"
    assert payload.bank_account is not None
    assert payload.bank_account.bank_name == "Standard Lesotho Bank"

    with pytest.raises(ValidationError):
        CompanyClientProfileUpdate.model_validate({"national_id": "029261283427"})


def test_rejection_requires_a_reason():
    with pytest.raises(ValidationError):
        CompanyClientNationalIdChangeDecision(approve=False)
    assert CompanyClientNationalIdChangeDecision(approve=True).approve is True


def test_national_id_normalisation_preserves_leading_zeroes():
    assert normalise_national_id(" 02 9261283427 ") == "029261283427"


def test_backend_declares_edit_and_dual_approval_routes():
    source = (BACKEND / "routers" / "company_clients.py").read_text(encoding="utf-8")
    account_source = (BACKEND / "routers" / "account.py").read_text(encoding="utf-8")
    assert '@router.patch("/{account_id}/profile"' in source
    assert '"/{account_id}/national-id-change-requests"' in source
    assert 'company-owner-decision' in source
    assert 'Only an active company owner may approve this request' in (
        BACKEND / "services" / "borrower_identity_change_service.py"
    ).read_text(encoding="utf-8")
    assert '"/national-id-change-requests/{request_id}/decision"' in account_source
    assert "National ID changes require approval from the borrower and a company owner" in account_source


def test_migration_creates_pending_request_guard_and_dual_approval_columns():
    migration = (
        BACKEND
        / "alembic"
        / "versions"
        / "y8m2n4p6q790_company_client_profile_edits_identity_approval.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "x7k1m3n5p680"' in migration
    assert "borrower_approved_at" in migration
    assert "company_owner_approved_at" in migration
    assert "uq_company_client_identity_change_pending_account" in migration
    assert "status = 'pending'" in migration


def test_frontend_exposes_per_field_editing_and_both_approval_surfaces():
    editor = (
        FRONTEND / "components" / "clients" / "company-client-profile-editor-cards.tsx"
    ).read_text(encoding="utf-8")
    account = (
        FRONTEND / "components" / "account" / "account-profile-page.tsx"
    ).read_text(encoding="utf-8")
    dialog = (
        FRONTEND / "components" / "clients" / "company-client-profile-dialog.tsx"
    ).read_text(encoding="utf-8")

    assert "EditableRow" in editor
    assert "Request dual approval" in editor
    assert "Approve as company owner" in editor
    assert "Bank verification reset" in editor
    assert "CompanyClientProfileEditorCards" in dialog
    assert "National ID change approval" in account
    assert "Approve ID change" in account
    assert "Protected identity field" in account
