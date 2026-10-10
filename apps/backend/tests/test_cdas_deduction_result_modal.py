from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "page.tsx"


def test_deduction_results_use_wide_table_modal() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'kind: "deductions"' in source
    assert 'CustomDialog' in source
    assert '!w-[96vw]' in source
    assert 'sm:!max-w-[96vw]' in source
    assert 'xl:!max-w-[1500px]' in source
    assert "DeductionResultsTable" in source
    assert "Agency name" in source
    assert "Type" in source
    assert "Effective month" in source
    assert "Reference no." in source
    assert "sticky top-0" in source


def test_all_cdas_results_use_loanhub_custom_modal() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'kind: "employee"' in source
    assert 'kind: "affordability"' in source
    assert 'readFeedback?.kind === "deductions"' in source
    assert 'import { CustomDialog } from "@/components/ui/custom-dialog";' in source
    assert '<CustomDialog' in source
    assert '<Dialog open={readFeedback !== null}' not in source


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

    assert "Search returned CDAS fields" in source
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
    assert "min-w-max" in source
    assert "const showItemCode = has(deductionItemCode);" in source
    assert ">Clear</button>" not in source
    assert "Clear" in source
    assert "print:hidden" in source


def test_employee_verification_uses_wide_cdas_table_modal() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "function EmployeeResultsTable" in source
    assert 'min-w-[1180px]' in source
    assert 'Employee number' in source
    assert 'Date of birth' in source
    assert 'Joining date' in source
    assert 'Termination date' in source
    assert '!w-[96vw]' in source
    assert 'readFeedback?.kind === "employee"' in source
    assert "<EmployeeResultsTable" in source


def test_cdas_custom_modal_has_full_height_body_and_sticky_footer() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert '!h-[92vh]' in source
    assert 'bodyClassName="flex min-h-0 flex-1 flex-col overflow-hidden bg-background"' in source
    assert 'lg:grid-cols-[280px_minmax(0,1fr)]' in source
    assert '<main className="min-h-0 overflow-auto p-4 sm:p-6 lg:p-8 print:p-0">' in source
    assert 'shrink-0 items-center justify-between gap-3 border-t bg-card/95' in source
    assert 'onClick={() => setReadFeedback(null)}' in source


def test_cdas_custom_modal_contains_workspace_menu() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'aria-label="CDAS modal actions"' in source
    assert "CDAS workspace" in source
    assert "Deduction Capture" in source
    assert "Deduction Review" in source
    assert "Deduction Approval" in source
    assert "Admin" in source
    assert "View Deductions" in source
    assert "View Active Deduction" in source
    assert "Review Own Deductions" in source
    assert "Check Affordability" in source
    assert "Requests remaining" in source
    assert 'lg:grid-cols-[280px_minmax(0,1fr)]' in source
    assert 'data-cdas-employee-form="true"' in source


def test_cdas_deduction_table_is_endpoint_aware() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert '"ItemCode", "ItemCodeID", "AgencyCode", "DeductionCode"' in source
    assert '"DeductionType");' not in source
    assert 'function deductionTypeLabel' in source
    assert 'if (numeric === 1) return "Loan";' in source
    assert 'if (numeric === 2) return "Policy";' in source
    assert 'const showItemCode = has(deductionItemCode);' in source
    assert 'const showAgency = has(deductionAgencyName);' in source
    assert 'const showType = has(deductionTypeLabel);' in source
    assert 'LoanHub shows only fields returned by this CDAS endpoint.' in source
    assert 'Search returned CDAS fields' in source


def test_cdas_expiry_is_only_provider_supplied_or_safely_calculated() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'TotalInstallment' in source
    assert 'installments - 1' in source
    assert '" (calculated)"' in source
    assert 'const showExpiry = has(deductionExpiry);' in source


def test_cdas_table_avoids_dash_only_columns() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert '{showItemCode ? <th' in source
    assert '{showAgency ? <th' in source
    assert '{showReference ? <th' in source
    assert '{showEffective ? <th' in source
    assert '{showExpiry ? <th' in source
    assert 'Not returned' in source


def test_cdas_modal_can_start_add_deduction_for_loaded_employee() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "Add Deduction" in source
    assert "PlusCircle" in source
    assert '/company/cdas/operations?action=register&employee=' in source
    assert "encodeURIComponent(employee?.EmployeeNo || normalizedEmployeeNo)" in source
    assert "canManage && normalizedEmployeeNo" in source
