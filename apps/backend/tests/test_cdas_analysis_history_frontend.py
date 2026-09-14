from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "page.tsx"
API = ROOT / "frontend" / "api" / "cdasBooking.ts"


def test_cdas_booking_centre_has_analysis_database_table_and_print_action():
    source = PAGE.read_text(encoding="utf-8")

    assert 'label: "Analysis History"' in source
    assert "CDAS Analysis Database" in source
    assert "Every distinct structured CDAS analysis" in source
    assert "Print full report" in source
    assert "downloadArchivedAnalysisReport" in source
    assert "Raw pasted CDAS text is never stored" in source


def test_cdas_analysis_history_uses_company_scoped_history_api():
    source = API.read_text(encoding="utf-8")

    assert '"/cdas-booking/analyses"' in source
    assert "/cdas-booking/analyses/${id}/report/pdf" in source
