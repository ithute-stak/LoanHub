from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "page.tsx"


def test_deduction_results_use_wide_table_modal() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'kind: "deductions"' in source
    assert 'w-[90vw] max-w-[90vw]' in source
    assert "DeductionResultsTable" in source
    assert "Deduction / agency name" in source
    assert "Effective month" in source
    assert "Reference no." in source
    assert "sticky top-0" in source


def test_employee_and_affordability_keep_compact_result_layout() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'kind: "employee"' in source
    assert 'kind: "affordability"' in source
    assert 'readFeedback?.kind === "deductions"' in source
    assert 'sm:max-w-4xl' in source


def test_known_cdas_agency_names_have_display_fallbacks() -> None:
    source = PAGE.read_text(encoding="utf-8")

    expected = {
        "2409": "L.A.T. Subscription",
        "2576": "LESOTHO TEACHERS TRADE UNION",
        "2261": "Gap Funeral Services",
        "2330": "Thusong Financial Services",
        "2355": "PALT Membership Subscriptions",
    }
    for code, name in expected.items():
        assert f'"{code}": "{name}"' in source

    assert "providerName" in source
    assert "KNOWN_CDAS_AGENCIES[code]" in source


def test_deduction_modal_has_search_sort_total_and_export_controls() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "Search code, deduction, reference or status" in source
    assert "Sort by amount" in source
    assert "visibleTotal" in source
    assert "Export CSV" in source
    assert "text/csv;charset=utf-8" in source
    assert "No deductions match the current search." in source


def test_workspace_keeps_deduction_results_compact_after_lookup() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "Results are kept compact here; open the full 90% table" in source
    assert source.count("View results") >= 2
    assert "View result" in source
    assert "openDeductionResults" in source
    assert "allDeductions.map((record, index)" not in source
    assert "ownDeductions.map((record, index)" not in source


def test_deduction_modal_10_of_10_operator_polish() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'Employee {employee?.EmployeeNo || normalizedEmployeeNo || "—"}' in source
    assert "[employee.Name, employee.Surname].filter(Boolean).join" in source
    assert "formatCdasPeriod" in source
    assert "deductionStatusClasses" in source
    assert "Print / Save PDF" in source
    assert 'onClick={() => window.print()}' in source
    assert "sticky left-0" in source
    assert "sticky left-[112px]" in source
    assert ">Clear</button>" not in source
    assert "Clear" in source
    assert "print:hidden" in source
    assert "print:shadow-none" in source
