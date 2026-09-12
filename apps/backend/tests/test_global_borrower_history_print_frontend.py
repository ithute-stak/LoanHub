from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOOKUP_COMPONENT = ROOT / "frontend" / "components" / "clients" / "global-borrower-lookup.tsx"
REPORT_HELPER = ROOT / "frontend" / "lib" / "borrower-history-report.ts"


def test_global_lookup_exposes_generate_and_print_history_action():
    source = LOOKUP_COMPONENT.read_text(encoding="utf-8")

    assert "Generate & print history" in source
    assert "generateAndPrintHistory" in source
    assert "window.open" in source
    assert "prepareDocumentGenerationWindow" in source
    assert "renderBorrowerHistoryReport" in source


def test_detailed_company_profile_is_loaded_only_for_linked_borrowers():
    source = LOOKUP_COMPONENT.read_text(encoding="utf-8")

    assert "result.already_company_client && result.company_client_account_id" in source
    assert "getCompanyClientProfile(result.company_client_account_id)" in source


def test_printable_report_contains_required_history_sections_and_privacy_scope():
    source = REPORT_HELPER.read_text(encoding="utf-8")

    required_sections = [
        "Borrower History Report",
        "Credit history summary",
        "Borrower profile",
        "Payment rating",
        "Loan history",
        "Documents register",
        "Comments and legal activity",
        "Report scope and privacy",
        "Other lenders' identities, documents, notes and internal records remain protected",
    ]

    for section in required_sections:
        assert section in source


def test_report_automatically_opens_browser_print_dialog():
    source = REPORT_HELPER.read_text(encoding="utf-8")

    assert "window.print()" in source
    assert "@page { size: A4 landscape" in source
    assert "save the report as PDF" in LOOKUP_COMPONENT.read_text(encoding="utf-8")
