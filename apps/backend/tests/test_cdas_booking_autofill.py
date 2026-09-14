from datetime import date

from routers.cdas_booking import CdasBookingAnalyseRequest, _analyze
from services.cdas_booking_autofill import parse_cdas_autofill_context


def test_autofill_reads_profile_values_from_following_lines():
    raw = """
**Employee No**Search
EMP-00917

**Name**
Mpho

**Surname**
Mokoena

**Gender**
Female

**NID**
123456789012

**Employer**
Ministry of Finance

**New Deduction Application**
**Agency**
**Agency *
2966
(Lelefa Debt Collection)**
"""

    context = parse_cdas_autofill_context(raw)

    assert context["profile"]["employee_no"] == "EMP-00917"
    assert context["profile"]["name"] == "Mpho"
    assert context["profile"]["surname"] == "Mokoena"
    assert context["profile"]["full_name"] == "Mpho Mokoena"
    assert context["profile"]["gender"] == "Female"
    assert context["profile"]["nid"] == "123456789012"
    assert context["profile"]["employer"] == "Ministry of Finance"
    assert context["application_context"]["new_deduction_agency_code"] == "2966"
    assert context["application_context"]["new_deduction_agency_name"] == "Lelefa Debt Collection"


def test_autofill_does_not_consume_the_next_label_when_value_is_missing():
    raw = """
Employee NoSearch
Name
Surname
Gender
Date of Birth
NID
Employer
Early Retirement Date 15/01/2037
Agency * 2966 (Lelefa Debt Collection)
"""

    context = parse_cdas_autofill_context(raw)

    assert context["profile"]["employee_no"] is None
    assert context["profile"]["name"] is None
    assert context["profile"]["surname"] is None
    assert context["profile"]["nid"] is None
    assert context["application_context"]["new_deduction_agency_code"] == "2966"
    assert context["application_context"]["new_deduction_agency_name"] == "Lelefa Debt Collection"


def test_autofill_supports_same_line_profile_values_and_search_noise():
    raw = """
Employee No: EMP-100 Search
Name: Lerato
Surname: Thamae
NID: 999999999999
Agency * 61433 (Lelefa Holdings)
"""

    context = parse_cdas_autofill_context(raw)

    assert context["profile"]["employee_no"] == "EMP-100"
    assert context["profile"]["full_name"] == "Lerato Thamae"
    assert context["profile"]["nid"] == "999999999999"
    assert context["application_context"]["new_deduction_agency_code"] == "61433"
    assert context["application_context"]["new_deduction_agency_name"] == "Lelefa Holdings"


def test_analyze_response_contains_values_used_by_frontend_autofill():
    raw = """
Employee NoSearch
EMP-4401
Name
Matekane
Surname
Molefe
NID
111222333444
Agency *
2966
(Lelefa Debt Collection)

| | 2907 | EXPRESS CREDIT | | M 1,463.00 | 2024-Nov | 2028-Oct | AP3027765 | Active |
"""

    analysis = _analyze(
        CdasBookingAnalyseRequest(
            raw_text=raw,
            booking_lead_months=6,
            own_item_codes=[],
            own_agency_names=[],
            as_of=date(2026, 9, 14),
        )
    )

    assert analysis["profile"]["full_name"] == "Matekane Molefe"
    assert analysis["profile"]["employee_no"] == "EMP-4401"
    assert analysis["profile"]["nid"] == "111222333444"
    assert analysis["application_context"]["current_cdas_agency_code"] == "2966"
    assert analysis["application_context"]["current_cdas_agency_name"] == "Lelefa Debt Collection"
    assert analysis["application_context"]["agency_auto_detected"] is True
