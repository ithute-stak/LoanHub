from datetime import date

from routers.cdas_booking import CdasBookingAnalyseRequest, _analyze
from services.cdas_booking_policy import apply_capacity_booking_policy
from services.cdas_booking_storage import dedupe_serialized_opportunities


FUTURE_BOOKING_CDAS = """
Max Available Deduction Amount: M 352.79
| | 2907 | EXPRESS CREDIT | | M 1,463.00 | 2024-Nov | 2028-Oct | AP3027765 | Active |
"""


def test_capacity_above_one_maloti_overrides_future_booking_window():
    analysis = _analyze(
        CdasBookingAnalyseRequest(
            raw_text=FUTURE_BOOKING_CDAS,
            booking_lead_months=1,
            own_item_codes=[],
            own_agency_names=[],
            amount_owing=10_000,
            as_of=date(2026, 9, 14),
        )
    )

    assert analysis["decision"] == "BOOK_NOW"
    assert analysis["next_possible_booking_date"] == "2026-09-01"
    assert analysis["capacity"]["booking_allowed"] is True
    assert analysis["capacity"]["assessed_available_amount"] == 352.79
    assert analysis["booking_term"]["amount_owing"] == 10_000
    assert analysis["booking_term"]["months_required"] == 29


def test_exactly_one_maloti_does_not_trigger_capacity_booking():
    analysis = {
        "decision": "WAIT_UNTIL",
        "decision_message": "wait",
        "next_possible_booking_date": "2028-09-01",
        "capacity": {
            "max_available_deduction_amount": 1.0,
            "max_available_after_selected_deductions": None,
        },
    }

    result = apply_capacity_booking_policy(
        analysis,
        as_of=date(2026, 9, 14),
        amount_owing=100,
    )

    assert result["decision"] == "WAIT_UNTIL"
    assert result["capacity"]["booking_allowed"] is False
    assert result["booking_term"]["months_required"] is None


def test_consolidation_after_selected_capacity_can_allow_booking():
    analysis = {
        "decision": "WAIT_UNTIL",
        "decision_message": "wait",
        "next_possible_booking_date": "2028-09-01",
        "capacity": {
            "max_available_deduction_amount": -352.79,
            "max_available_after_selected_deductions": 480.25,
        },
    }

    result = apply_capacity_booking_policy(
        analysis,
        as_of=date(2026, 9, 14),
        amount_owing=1_000,
    )

    assert result["decision"] == "BOOK_NOW"
    assert result["capacity"]["assessed_available_amount"] == 480.25
    assert result["booking_term"]["months_required"] == 3


def test_duplicate_cards_with_same_cdas_reference_collapse_to_richer_record():
    generic = {
        "id": "generic",
        "state": "UPCOMING",
        "client_name": None,
        "client_reference": None,
        "opportunity_reference_no": "AP3027765",
        "opportunity_item_code": "2907",
        "opportunity_expiry_date": "2028-10-01",
    }
    named = {
        "id": "named",
        "state": "UPCOMING",
        "client_name": "JEREMANE LETSELA",
        "client_reference": "EMP-1",
        "opportunity_reference_no": "AP3027765",
        "opportunity_item_code": "2907",
        "opportunity_expiry_date": "2028-10-01",
    }

    result = dedupe_serialized_opportunities([generic, named])

    assert len(result) == 1
    assert result[0]["id"] == "named"


def test_different_cdas_references_remain_separate():
    first = {
        "id": "one",
        "state": "UPCOMING",
        "client_name": "Client One",
        "client_reference": "EMP-1",
        "opportunity_reference_no": "AP3027765",
        "opportunity_item_code": "2907",
        "opportunity_expiry_date": "2028-10-01",
    }
    second = {
        "id": "two",
        "state": "UPCOMING",
        "client_name": "Client Two",
        "client_reference": "EMP-2",
        "opportunity_reference_no": "AP9999999",
        "opportunity_item_code": "2907",
        "opportunity_expiry_date": "2028-10-01",
    }

    result = dedupe_serialized_opportunities([first, second])

    assert len(result) == 2
