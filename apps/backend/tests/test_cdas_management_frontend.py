from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CDAS_ROOT = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas"
OPERATIONS = CDAS_ROOT / "operations" / "page.tsx"
DOCUMENTS = CDAS_ROOT / "documents" / "page.tsx"
SETTINGS = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "settings" / "_components" / "company-cdas-settings.tsx"


def test_deduction_operations_are_management_only_and_confirmed() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")

    assert "COMPANY_MANAGEMENT_ROLES" in source
    assert "if (!canManage)" in source
    assert '"/cdas/deductions/lifecycle"' in source
    assert '"/cdas/deductions/modify-active"' in source
    assert '"/cdas/deductions/settle"' in source
    assert source.count("confirmed") >= 12
    assert "explicitly confirms the action" in source
    assert "useEffect" not in source


def test_operations_preserve_documented_ambiguous_cancel_reject_code() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")

    assert '[6, "Cancel / Reject"]' in source
    assert "document assigns code 6 to both Cancelled and Reject" in source
    for reason in (
        "Policy Expired",
        "Paid By Employee",
        "Consolidation",
        "Deceased Employee",
    ):
        assert reason in source


def test_document_retrieval_is_manual_management_only() -> None:
    source = DOCUMENTS.read_text(encoding="utf-8")

    assert "COMPANY_MANAGEMENT_ROLES" in source
    assert 'api.post<DocumentResponse>("/cdas/documents"' in source
    assert "onSubmit={retrieveDocument}" in source
    assert "useEffect" not in source
    assert "1 — Output File" in source
    assert "2 — Statement" in source
    assert "Reports not ready yet" in source
    assert "DocumentTye" in source


def test_settings_describe_full_manual_integration_without_background_polling() -> None:
    source = SETTINGS.read_text(encoding="utf-8")

    assert 'reintegration_phase: "manual_documented_operations"' in source
    assert "no background CDAS crawling or automatic lifecycle processing is enabled" in source
    assert 'href="/company/cdas"' in source
    assert "authentication-only" not in source.lower()
