"""Historical CDAS preview must never affect financial state."""
import pytest
from services.cdas_historical_import import preview_cdas_history_csv, reconcile_preview_rows


HEADER = "Employee No,Employee Name,Monthly Amount,Total Installment,Principal Amount,Starting Month,Ending Month,Policy Ref. No\n"


def test_valid_rows_deduplicated_with_source_provenance():
    row = "0066128,LIAU,179,3,537,Oct-2026,Dec-2026,0066128 2966\n"
    result = preview_cdas_history_csv((HEADER + row + row).encode())
    assert result["persisted"] is False
    assert result["valid_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["rows"][0]["employee_no"] == "0066128"


def test_invalid_amount_is_not_accepted():
    result = preview_cdas_history_csv((HEADER + "0066128,LIAU,-179,3,537,Oct-2026,Dec-2026,ABC\n").encode())
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 1


def test_missing_headers_fail_closed():
    with pytest.raises(ValueError, match="Missing CDAS columns"):
        preview_cdas_history_csv(b"employee,amount\nabc,100\n")


def test_oversized_file_fails_closed():
    with pytest.raises(ValueError, match="exceeds 2 MB"):
        preview_cdas_history_csv(b"x" * 2_000_001)


def test_reconciliation_requires_exact_employee_and_reference():
    rows = [{"employee_no": "001234", "policy_reference": "POL-A", "monthly_amount": "100.00"}]
    mandates = [{"id": "m1", "employee_no": "001234", "mandate_number": "POL-A",
                 "external_reference": None, "monthly_amount": "100.00"}]
    result = reconcile_preview_rows(rows, mandates)
    assert result["counts"]["exact_match"] == 1
    assert result["decisions"][0]["matched_mandate_id"] == "m1"
    assert result["persisted"] is False


def test_amount_conflict_is_flagged_not_automatically_accepted():
    rows = [{"employee_no": "001234", "policy_reference": "POL-A", "monthly_amount": "101"}]
    mandates = [{"id": "m1", "employee_no": "001234", "mandate_number": "POL-A",
                 "external_reference": None, "monthly_amount": "100"}]
    assert reconcile_preview_rows(rows, mandates)["counts"]["conflict"] == 1


def test_same_employee_without_reference_requires_review():
    rows = [{"employee_no": "001234", "policy_reference": "OLD", "monthly_amount": "100"}]
    mandates = [{"id": "m1", "employee_no": "001234", "mandate_number": "NEW",
                 "external_reference": None, "monthly_amount": "100"}]
    result = reconcile_preview_rows(rows, mandates)
    assert result["counts"]["manual_review"] == 1
    assert result["decisions"][0]["matched_mandate_id"] is None
