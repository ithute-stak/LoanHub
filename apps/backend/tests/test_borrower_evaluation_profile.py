from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from database.models.enums import EmploymentStatus
from database.schemas.borrower import BorrowerUpdate
from services.borrower_profile_service import build_borrower_evaluation


ROOT = Path(__file__).resolve().parents[2]


def _borrower(**overrides):
    values = {
        "employment_status": EmploymentStatus.EMPLOYED,
        "employer_name": "Ithute Solutions",
        "job_title": "Engineer",
        "employment_start_date": None,
        "monthly_income": Decimal("10000"),
        "net_monthly_income": Decimal("8000"),
        "other_monthly_income": Decimal("500"),
        "monthly_living_expenses": Decimal("3000"),
        "monthly_debt_repayments": Decimal("1000"),
        "has_existing_loans": True,
        "residential_status": "tenant",
        "bank_name": "FNB Lesotho",
        "account_last_four": "1234",
        "consent_to_share_profile": True,
        "consent_to_share_documents": True,
        "consent_to_credit_checks": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _person():
    return SimpleNamespace(
        national_id="123456789012",
        passport_number=None,
        district="Maseru",
        town_or_village="Maseru",
        physical_address="Kingsway",
    )


def _evidence():
    return [
        SimpleNamespace(category="borrower_identity"),
        SimpleNamespace(category="borrower_proof_of_address"),
        SimpleNamespace(category="borrower_payslip"),
        SimpleNamespace(category="borrower_bank_statement"),
    ]


def test_evaluation_builds_explainable_affordability_totals():
    result = build_borrower_evaluation(_borrower(), _person(), _evidence())

    assert result["total_monthly_income"] == Decimal("8500")
    assert result["total_monthly_commitments"] == Decimal("4000")
    assert result["disposable_monthly_income"] == Decimal("4500")
    assert result["debt_to_income_percent"] == Decimal("11.76")
    assert result["profile_completeness"] == 100
    assert result["missing_requirements"] == []


def test_evaluation_never_turns_missing_income_into_a_decision():
    result = build_borrower_evaluation(
        _borrower(
            monthly_income=None,
            net_monthly_income=None,
            other_monthly_income=0,
            monthly_living_expenses=0,
            consent_to_share_documents=False,
        ),
        _person(),
        [],
    )

    assert result["debt_to_income_percent"] is None
    assert result["disposable_monthly_income"] == Decimal("-1000")
    assert "Monthly income" in result["missing_requirements"]
    assert "Evidence-sharing consent" in result["missing_requirements"]


@pytest.mark.parametrize(
    "payload",
    [
        {"account_last_four": "123"},
        {"account_last_four": "12A4"},
        {"monthly_living_expenses": Decimal("-0.01")},
        {"monthly_debt_repayments": Decimal("-1")},
        {"dependants": 51},
    ],
)
def test_borrower_evaluation_rejects_unsafe_or_invalid_values(payload):
    with pytest.raises(ValidationError):
        BorrowerUpdate(**payload)


def test_evidence_upload_and_download_are_consent_and_relationship_guarded():
    files_router = (ROOT / "backend" / "routers" / "files.py").read_text(encoding="utf-8")
    file_service = (ROOT / "backend" / "services" / "file_service.py").read_text(
        encoding="utf-8"
    )

    assert 'linked_entity_type == "borrower_evaluation"' in files_router
    assert "borrower.user_id == context.user.id" in files_router
    assert "CompanyBorrowerAccount.borrower_id == borrower_id" in files_router
    assert 'visibility = "private"' in files_router
    assert "is_confidential = True" in files_router

    assert "borrower.consent_to_share_documents" in file_service
    assert "context.staff.role not in LENDING_ROLES" in file_service
    assert "CompanyBorrowerAccount.borrower_id == borrower.id" in file_service
    assert "DirectLoanApplication.borrower_id == borrower.id" in file_service
    assert "ClientCompanyLoan.borrower_id == borrower.id" in file_service
    assert "company_has_request_access" in file_service


def test_profile_ui_is_a_seven_tab_shared_assessment_with_multiple_records():
    profile = (
        ROOT / "frontend" / "app" / "(dashboard)" / "borrower" / "profile" / "page.tsx"
    ).read_text(encoding="utf-8")
    evidence = (
        ROOT
        / "frontend"
        / "components"
        / "borrower"
        / "borrower-evaluation-evidence.tsx"
    ).read_text(encoding="utf-8")

    expected_tabs = [
        "Application",
        "KYC",
        "Employment",
        "Expenses & debt",
        "Banking",
        "Affordability",
        "Review & activity",
    ]
    for label in expected_tabs:
        assert label in profile

    assert "getMyFinancialProfile" in profile
    assert "saveMyFinancialProfile" in profile
    assert "getMyProfileActivity" in profile
    assert "bankAccounts" in profile
    assert "Add account" in profile
    assert "activity.map" in profile
    assert "Shared facts, private agreements." in profile
    assert 'linkedEntityType: "borrower_evaluation"' in evidence
    assert 'multiple' in evidence.lower()
    assert "onEvidenceChange" in evidence


def test_assessment_models_are_borrower_wide_but_agreements_stay_company_scoped():
    models = (ROOT / "backend" / "database" / "models" / "origination.py").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "backend" / "services" / "origination_service.py").read_text(
        encoding="utf-8"
    )

    assert 'UniqueConstraint("borrower_id", name="uq_kyc_borrower")' in models
    assert 'UniqueConstraint("borrower_id", name="uq_employment_borrower")' in models
    assert "company_id = Column(" in models
    assert 'ondelete="SET NULL"' in models
    assert '"bank_accounts": bank_payloads' in service
    assert "BorrowerBankAccount.borrower_id == borrower_id" in service
    assert "LoanContract" in models
    assert 'ForeignKey("loan_companies.id", ondelete="CASCADE")' in models
