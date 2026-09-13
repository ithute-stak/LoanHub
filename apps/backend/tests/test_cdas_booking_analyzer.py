from datetime import date

from services.cdas_booking_analyzer import analyse_cdas_booking, parse_cdas_text


SAMPLE_CDAS = """
| Item CodeAgency NameSeq. No.Ded. Amt.Eff. DateExp. DateRef. No.Status | | | | | | | | |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | 2561 | Lesana Lesotho Limited | | M 3,942.08 | 2026-Mar | 2027-Aug | 1000093084 | Active |
| | 2595 | First National Bank of Lesotho | | M 21,011.86 | 2024-Jan | 2028-Dec | FNB LOAN 62592936979 | Active |
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
    assert result["total_monthly_deductions"] == 24953.94


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
