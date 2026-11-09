from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quick_loan_offer_no_longer_requires_affordability():
    router = _read(ROOT / "routers/loan_offers.py")
    service = _read(ROOT / "services/loan_service.py")
    assert "_calculate_offer_terms(" in router
    assert '@router.post("/quick-affordability-preview")' not in router
    assert "_quick_affordability_for_terms(" not in router
    assert 'if not affordability["passed"]:' not in router
    accept_block = service.split("def accept_offer(", 1)[1].split("def _cash_reference", 1)[0]
    assert '"quick_affordability"' not in accept_block


def test_marketplace_ui_does_not_require_affordability_or_at_risk_override():
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/marketplace/_components/marketplace-request-dialog.tsx"
    )
    assert "Submit loan offer" in page
    assert "previewQuickLoanAffordability" not in page
    assert "Approve at own risk" not in page
    assert "affordabilityChecking" not in page


def test_origination_submission_does_not_require_affordability():
    router = _read(ROOT / "routers/origination.py")
    wizard = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/new/page.tsx")
    readiness = _read(ROOT / "services/lending_integration_service.py")
    submit = router.split('def submit_application(', 1)[1].split('@router.post(', 1)[0]
    assert "A positive affordability assessment is required" not in submit
    assert 'label: "Affordability"' not in wizard
    assert 'label: "Review & submit"' in wizard
    assert "affordability_not_positive" not in readiness
    assert "top_up_affordability_outdated" not in readiness


def test_quick_affordability_uses_rust_and_java_only_after_exact_parity(monkeypatch) -> None:
    from decimal import Decimal
    from types import SimpleNamespace
    from uuid import uuid4

    from services import quick_loan_affordability_service as affordability

    borrower = SimpleNamespace(
        net_monthly_income=Decimal("5000.00"),
        monthly_income=Decimal("5000.00"),
        other_monthly_income=Decimal("500.00"),
        monthly_living_expenses=Decimal("1200.00"),
        monthly_debt_repayments=Decimal("600.00"),
        dependants=2,
    )
    policy = SimpleNamespace(
        id=uuid4(),
        version=3,
        dependant_allowance=Decimal("250.00"),
        living_expense_buffer=Decimal("300.00"),
        disposable_income_usage_percent=Decimal("80"),
        max_dti_percent=Decimal("40"),
        max_installment_income_percent=Decimal("35"),
        min_verified_net_income=Decimal("2000.00"),
        min_disposable_after_installment=Decimal("500.00"),
    )
    rust_result = {
        "passed": True,
        "monthly_income": "5500.00",
        "base_income": "5000.00",
        "other_income": "500.00",
        "living_expenses": "1200.00",
        "existing_debt_repayments": "600.00",
        "dependant_allowance_total": "500.00",
        "configured_buffer": "300.00",
        "disposable_before_new_loan": "2900.00",
        "proposed_installment": "700.00",
        "maximum_affordable_installment": "1600.00",
        "affordability_headroom": "900.00",
        "disposable_after_installment": "2200.00",
        "dti_percent": "23.636",
        "disposable_income_limit": "2320.00",
        "dti_limit": "1600.00",
        "installment_income_limit": "1925.00",
        "minimum_disposable_after_installment": "500.00",
        "income_missing": False,
        "income_below_minimum": False,
        "installment_above_limit": False,
        "disposable_income_too_low": False,
        "authoritative": False,
    }
    java_result = {
        "passed": True,
        "decision": "pass",
        "reasons": [
            {
                "severity": "pass",
                "code": "income_ok",
                "message": "Monthly income meets the lender's configured minimum.",
            },
            {
                "severity": "pass",
                "code": "installment_within_limit",
                "message": "The proposed installment is within the calculated affordability limit.",
            },
        ],
        "authoritative": False,
    }

    monkeypatch.setattr(
        affordability,
        "workload_routing_mode",
        lambda workload: "prefer-worker",
    )
    monkeypatch.setattr(
        affordability,
        "rust_affordability_assessment",
        lambda **kwargs: rust_result,
    )
    monkeypatch.setattr(
        affordability,
        "java_underwriting_rules",
        lambda **kwargs: java_result,
    )

    result = affordability.quick_loan_affordability(
        borrower=borrower,
        policy=policy,
        proposed_installment=Decimal("700.00"),
    )

    assert result["passed"] is True
    assert result["maximum_affordable_installment"] == "1600.00"
    assert result["compute_runtime"]["rust_parity"] == "match"
    assert result["compute_runtime"]["rust_used"] is True
    assert result["compute_runtime"]["java_parity"] == "match"
    assert result["compute_runtime"]["java_used"] is True
    assert result["compute_runtime"]["python_authority"] is True


def test_quick_affordability_worker_mismatch_keeps_python_authority(monkeypatch) -> None:
    from decimal import Decimal
    from types import SimpleNamespace
    from uuid import uuid4

    from services import quick_loan_affordability_service as affordability

    borrower = SimpleNamespace(
        net_monthly_income=Decimal("5000.00"),
        monthly_income=Decimal("5000.00"),
        other_monthly_income=Decimal("0.00"),
        monthly_living_expenses=Decimal("1000.00"),
        monthly_debt_repayments=Decimal("500.00"),
        dependants=0,
    )
    policy = SimpleNamespace(
        id=uuid4(),
        version=1,
        dependant_allowance=Decimal("0.00"),
        living_expense_buffer=Decimal("0.00"),
        disposable_income_usage_percent=Decimal("80"),
        max_dti_percent=Decimal("40"),
        max_installment_income_percent=Decimal("35"),
        min_verified_net_income=Decimal("2000.00"),
        min_disposable_after_installment=Decimal("500.00"),
    )
    mismatches: list[str] = []

    monkeypatch.setattr(
        affordability,
        "workload_routing_mode",
        lambda workload: "prefer-worker",
    )
    monkeypatch.setattr(
        affordability,
        "rust_affordability_assessment",
        lambda **kwargs: {
            "passed": True,
            "monthly_income": "9999.00",
            "authoritative": False,
        },
    )
    monkeypatch.setattr(
        affordability,
        "java_underwriting_rules",
        lambda **kwargs: {
            "passed": False,
            "decision": "fail",
            "reasons": [],
            "authoritative": False,
        },
    )
    monkeypatch.setattr(
        affordability,
        "record_parity_mismatch",
        lambda worker: mismatches.append(worker),
    )

    result = affordability.quick_loan_affordability(
        borrower=borrower,
        policy=policy,
        proposed_installment=Decimal("500.00"),
    )

    assert result["monthly_income"] == "5000.00"
    assert result["compute_runtime"]["rust_used"] is False
    assert result["compute_runtime"]["rust_parity"] == "mismatch"
    assert result["compute_runtime"]["java_used"] is False
    assert result["compute_runtime"]["java_parity"] == "mismatch"
    assert result["compute_runtime"]["python_authority"] is True
    assert mismatches == ["rust_compute", "java_worker"]
