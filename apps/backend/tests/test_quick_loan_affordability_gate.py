from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quick_loan_offer_requires_affordability_before_approval() -> None:
    router = _read(ROOT / "routers/loan_offers.py")
    service = _read(ROOT / "services/quick_loan_affordability_service.py")

    assert '@router.post("/quick-affordability-preview")' in router
    assert "_quick_affordability_for_terms(" in router
    assert 'if not affordability["passed"]:' in router
    assert "The borrower did not pass affordability for these offer terms." in router
    assert "def quick_loan_affordability(" in service
    assert '"decision": "pass" if passed else "fail"' in service
    assert '"maximum_affordable_installment"' in service
    assert '"disposable_after_installment"' in service
    assert '"dti_percent"' in service


def test_failed_quick_affordability_needs_authorized_own_risk_override() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    assert "payload.approve_at_own_risk" in router
    assert "context.role not in COMPANY_MANAGEMENT_ROLES" in router
    assert "policy.manager_override_enabled" in router
    assert "len(own_risk_reason) < 10" in router
    assert '"manager_at_own_risk_override"' in router
    assert '"approved_by_user_id": str(context.user.id)' in router
    assert '"approved_at": datetime.now(timezone.utc).isoformat()' in router


def test_quick_offer_edits_recheck_affordability() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    update_block = router.split("def update_offer(", 1)[1].split("@router.post", 1)[0]
    assert "_quick_affordability_for_terms(" in update_block
    assert "approve_at_own_risk" in update_block
    assert '"quick_affordability"' in update_block


def test_quick_offer_acceptance_requires_recorded_affordability_decision() -> None:
    service = _read(ROOT / "services/loan_service.py")

    accept_block = service.split("def accept_offer(", 1)[1].split("def _cash_reference", 1)[0]
    assert '"quick_affordability"' in accept_block
    assert "The lender must refresh this quick-loan offer" in accept_block
    assert "failed affordability and has no authorized at-risk approval" in accept_block


def test_marketplace_ui_shows_loanable_or_at_risk_choice() -> None:
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/marketplace/_components/marketplace-request-dialog.tsx"
    )

    assert "Affordability decision" in page
    assert "LOANABLE" in page
    assert "NOT LOANABLE" in page
    assert "Approve at own risk" in page
    assert "This is an explicit management exception." in page
    assert "previewQuickLoanAffordability" in page
    assert "approve_at_own_risk" in page
    assert "own_risk_reason" in page



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
