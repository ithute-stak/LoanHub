from datetime import date

from routers.cdas_booking import CdasBookingAnalyseRequest, _analyze


CURRENT_AGENCY_SCREEN = """
**Max Available Deduction Amount: M 500.00**

| | 3333 | Lelefa Debt Collection | | M 250.00 | 2026-Jan | 2027-Dec | LELEFA-001 | Active |

**New Deduction Application**
**Agency**
**Agency * 2966 (Lelefa Debt Collection)**
"""


def test_detected_current_cdas_agency_is_automatically_treated_as_ours():
    result = _analyze(
        CdasBookingAnalyseRequest(
            raw_text=CURRENT_AGENCY_SCREEN,
            as_of=date(2026, 9, 14),
            booking_lead_months=6,
            own_item_codes=[],
            own_agency_names=[],
        )
    )

    assert result["application_context"]["current_cdas_agency_code"] == "2966"
    assert result["application_context"]["current_cdas_agency_name"] == "Lelefa Debt Collection"
    assert result["application_context"]["agency_auto_detected"] is True
    assert result["decision"] == "ALREADY_BOOKED"
    assert len(result["own_bookings"]) == 1
    assert result["own_bookings"][0]["agency_name"] == "Lelefa Debt Collection"
    assert result["own_bookings"][0]["is_own_booking"] is True
