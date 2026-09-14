from datetime import date

from services.cdas_booking_analyzer import (
    analyse_cdas_booking,
    parse_cdas_screen_context,
    parse_cdas_text,
)


SAMPLE_CDAS = """
| Item CodeAgency NameSeq. No.Ded. Amt.Eff. DateExp. DateRef. No.Status | | | | | | | | |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | 2561 | Lesana Lesotho Limited | | M 3,942.08 | 2026-Mar | 2027-Aug | 1000093084 | Active |
| | 2595 | First National Bank of Lesotho | | M 21,011.86 | 2024-Jan | 2028-Dec | FNB LOAN 62592936979 | Active |
"""

DATE_CONFLICT_CDAS = """
| | 2419 | Les.Nnational Insurance - 9 | | M 30.00 | 2024-Apr | 2019-Jan | 9536836 | Active |
"""

MIXED_CDAS = """
| | 2180 | Netloans (pty) Ltd - 2 | | M 132.00 | 2026-Jul | 2034-May | 45150 | Active |
| | 2419 | Les.Nnational Insurance - 9 | | M 30.00 | 2024-Apr | 2019-Jan | 9536836 | Active |
| | 2890 | PLATINUM CREDIT LTD | | M 4,622.57 | 2025-Oct | 2033-Sep | BNP1000000146 | Active |
"""

FULL_CDAS_SCREEN = """
**Employee No**Search

**Name**

**Surname**

**Gender**

**Date of Birth**

**NID**

**Employer**

**Joining Date**

**End Date**

**Early Retirement Date**   15/01/2037

**Compulsory Retirement Date**   15/01/2047

**Max Available Deduction Amount:   -352.79**

**New Consolidation Application**

Max available after deleting the selected deductions: -M 352.79

**Description**

| Item CodeAgency NameSeq. No.Ded. Amt.Eff. DateExp. DateRef. No.Status |      |                             |   |            |          |          |           |        |
| --------------------------------------------------------------------- | ---- | --------------------------- | - | ---------- | -------- | -------- | --------- | ------ |
|                                                                       | 2907 | EXPRESS CREDIT              |   | M 1,463.00 | 2024-Nov | 2028-Oct | AP3027765 | Active |
|                                                                       | 2180 | Netloans (pty) Ltd - 2      |   | M 463.00   | 2026-Sep | 2032-Nov | 39607     | Active |
|                                                                       | 2340 | Alliance Insurance - 1      |   | M 145.00   | 2024-Aug |          | 31092     | Active |
|                                                                       | 2419 | Les.Nnational Insurance - 9 |   | M 110.00   | 2023-Apr | 2019-Jan | 9531222   | Active |

**New Deduction Application**

**Agency**

**Agency *                                                       2966                                        (Lelefa Debt Collection)**
"""


def test_parse_markdown_cdas_rows():
    rows = parse_cdas_text(SAMPLE_CDAS)

    assert len(rows) == 2
    assert rows[0]["item_code"] == "2561"
    assert rows[0]["agency_name"] == "Lesana Lesotho Limited"
    assert rows[0]["deduction_amount"] == 3942.08
    assert rows[0]["effective_date"] == date(2026, 3, 1)
    assert rows[0]["expiry_date"] == date(2027, 8, 1)
    assert rows[1]["reference_no"] == "FNB LOAN 62592936979"


def test_next_booking_date_uses_earliest_competitor_window():
    result = analyse_cdas_booking(
        SAMPLE_CDAS,
        as_of=date(2026, 9, 13),
        booking_lead_months=6,
    )

    assert result["decision"] == "WAIT_UNTIL"
    assert result["next_possible_booking_date"] == "2027-02-01"
    assert result["opportunity"]["agency_name"] == "Lesana Lesotho Limited"
    assert result["reported_active_monthly_deductions"] == 24953.94
    assert result["total_monthly_deductions"] == 24953.94
    assert result["data_quality_issue_count"] == 0


def test_own_item_code_reports_existing_booking_duration():
    result = analyse_cdas_booking(
        SAMPLE_CDAS,
        as_of=date(2026, 9, 13),
        booking_lead_months=6,
        own_item_codes=["2561"],
    )

    assert result["decision"] == "ALREADY_BOOKED"
    own = result["own_bookings"][0]
    assert own["agency_name"] == "Lesana Lesotho Limited"
    assert own["elapsed_months"] == 6
    assert own["months_to_expiry"] == 11
    assert own["scheduled_deduction_months"] == 18
    assert own["booking_status"] == "BOOKED_BY_US"


def test_own_agency_name_can_identify_booking():
    result = analyse_cdas_booking(
        SAMPLE_CDAS,
        as_of=date(2026, 9, 13),
        own_agency_names=["  LESANA   LESOTHO LIMITED "],
    )

    assert result["decision"] == "ALREADY_BOOKED"
    assert result["own_monthly_deductions"] == 3942.08


def test_plain_text_row_is_supported():
    raw = "2561 Lesana Lesotho Limited M 3,942.08 2026-Mar 2027-Aug 1000093084 Active"
    rows = parse_cdas_text(raw)

    assert len(rows) == 1
    assert rows[0]["item_code"] == "2561"
    assert rows[0]["deduction_amount"] == 3942.08


def test_active_row_with_expiry_before_effective_date_requires_review():
    result = analyse_cdas_booking(
        DATE_CONFLICT_CDAS,
        as_of=date(2026, 9, 14),
        booking_lead_months=6,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["next_possible_booking_date"] is None
    assert result["reported_active_monthly_deductions"] == 30.0
    assert result["total_monthly_deductions"] == 0
    assert result["excluded_monthly_deductions"] == 30.0
    assert result["data_quality_issue_count"] == 1

    row = result["deductions"][0]
    assert row["item_code"] == "2419"
    assert row["reported_active"] is True
    assert row["is_active"] is False
    assert row["excluded_from_booking"] is True
    assert row["data_quality_status"] == "DATE_CONFLICT"
    assert row["booking_status"] == "DATA_CONFLICT"
    assert row["booking_open_date"] is None
    assert row["months_until_booking"] is None


def test_date_conflict_is_excluded_while_valid_rows_still_drive_booking():
    result = analyse_cdas_booking(
        MIXED_CDAS,
        as_of=date(2026, 9, 14),
        booking_lead_months=6,
    )

    assert result["decision"] == "WAIT_UNTIL"
    assert result["next_possible_booking_date"] == "2033-03-01"
    assert result["opportunity"]["item_code"] == "2890"
    assert result["reported_active_monthly_deductions"] == 4784.57
    assert result["total_monthly_deductions"] == 4754.57
    assert result["competitor_monthly_deductions"] == 4754.57
    assert result["excluded_monthly_deductions"] == 30.0
    assert result["data_quality_issue_count"] == 1
    assert result["data_quality_issues"][0]["item_code"] == "2419"


def test_invalid_own_item_code_does_not_claim_already_booked():
    result = analyse_cdas_booking(
        DATE_CONFLICT_CDAS,
        as_of=date(2026, 9, 14),
        booking_lead_months=6,
        own_item_codes=["2419"],
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["own_bookings"] == []
    assert result["own_monthly_deductions"] == 0


def test_full_cdas_screen_extracts_profile_capacity_retirement_and_agency():
    context = parse_cdas_screen_context(FULL_CDAS_SCREEN, as_of=date(2026, 9, 14))

    assert context["profile"]["employee_no"] is None
    assert context["profile"]["early_retirement_date"] == "2037-01-15"
    assert context["profile"]["compulsory_retirement_date"] == "2047-01-15"
    assert context["capacity"]["max_available_deduction_amount"] == -352.79
    assert context["capacity"]["max_available_after_selected_deductions"] == -352.79
    assert context["capacity"]["status"] == "NEGATIVE_AVAILABLE"
    assert context["capacity"]["shortfall_amount"] == 352.79
    assert context["application_context"]["new_deduction_agency_code"] == "2966"
    assert context["application_context"]["new_deduction_agency_name"] == "Lelefa Debt Collection"
    assert context["retirement_analysis"]["days_until_early_retirement"] > 0


def test_full_cdas_screen_keeps_incomplete_and_conflicting_rows_for_financial_analysis():
    result = analyse_cdas_booking(
        FULL_CDAS_SCREEN,
        as_of=date(2026, 9, 14),
        booking_lead_months=6,
    )

    assert len(result["deductions"]) == 4
    assert result["decision"] == "WAIT_UNTIL"
    assert result["next_possible_booking_date"] == "2028-04-01"
    assert result["opportunity"]["item_code"] == "2907"
    assert result["reported_active_monthly_deductions"] == 2181.0
    assert result["total_monthly_deductions"] == 1926.0
    assert result["excluded_monthly_deductions"] == 255.0
    assert result["data_quality_issue_count"] == 2

    by_code = {row["item_code"]: row for row in result["deductions"]}
    assert by_code["2340"]["data_quality_status"] == "MISSING_EXPIRY"
    assert by_code["2340"]["expiry_date"] is None
    assert by_code["2340"]["booking_status"] == "DATA_INCOMPLETE"
    assert by_code["2419"]["data_quality_status"] == "DATE_CONFLICT"
    assert by_code["2419"]["booking_status"] == "DATA_CONFLICT"
