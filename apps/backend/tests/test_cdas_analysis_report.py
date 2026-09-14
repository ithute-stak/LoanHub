from uuid import uuid4

from database.models.company import LoanCompany
from services.cdas_analysis_report_service import (
    _flatten_structured_analysis,
    build_cdas_analysis_pdf,
    cdas_report_filename,
)


def _analysis() -> dict:
    opportunity = {
        "item_code": "2907",
        "agency_name": "EXPRESS CREDIT",
        "deduction_amount": 1463.0,
        "effective_date": "2024-11-01",
        "expiry_date": "2028-10-01",
        "reference_no": "AP3027765",
        "status": "Active",
        "reported_active": True,
        "is_own_booking": False,
        "is_active": True,
        "excluded_from_booking": False,
        "data_quality_status": "OK",
        "data_quality_message": None,
        "elapsed_months": 22,
        "months_to_expiry": 25,
        "scheduled_deduction_months": 48,
        "booking_open_date": "2028-04-01",
        "months_until_booking": 19,
        "booking_status": "WAIT",
    }
    conflict = {
        "item_code": "2419",
        "agency_name": "Les.Nnational Insurance - 9",
        "deduction_amount": 110.0,
        "effective_date": "2023-04-01",
        "expiry_date": "2019-01-01",
        "reference_no": "9531222",
        "status": "Active",
        "reported_active": True,
        "is_own_booking": False,
        "is_active": False,
        "excluded_from_booking": True,
        "data_quality_status": "DATE_CONFLICT",
        "data_quality_message": "Effective month 2023-04 is later than expiry month 2019-01.",
        "elapsed_months": None,
        "months_to_expiry": None,
        "scheduled_deduction_months": None,
        "booking_open_date": None,
        "months_until_booking": None,
        "booking_status": "DATA_CONFLICT",
    }
    return {
        "as_of": "2026-09-14",
        "booking_lead_months": 6,
        "profile": {
            "employee_no": "EMP-4401",
            "name": "Matekane",
            "surname": "Molefe",
            "full_name": "Matekane Molefe",
            "gender": "Female",
            "date_of_birth": "1990-01-15",
            "nid": "111222333444",
            "employer": "Ministry of Finance",
            "joining_date": "2018-03-01",
            "end_date": None,
            "early_retirement_date": "2037-01-15",
            "compulsory_retirement_date": "2047-01-15",
        },
        "capacity": {
            "max_available_deduction_amount": 500.0,
            "max_available_after_selected_deductions": None,
            "assessed_available_amount": 500.0,
            "booking_threshold_amount": 1.0,
            "booking_allowed": True,
            "status": "AVAILABLE",
            "shortfall_amount": 0.0,
        },
        "booking_term": {
            "amount_owing": 4600.0,
            "monthly_available_deduction": 500.0,
            "months_required": 10,
            "calculation": "ceil(amount_owing / monthly_available_deduction)",
        },
        "retirement_analysis": {
            "early_retirement_date": "2037-01-15",
            "compulsory_retirement_date": "2047-01-15",
            "days_until_early_retirement": 3775,
            "days_until_compulsory_retirement": 7428,
        },
        "application_context": {
            "new_deduction_agency_code": "2966",
            "new_deduction_agency_name": "Lelefa Debt Collection",
            "current_cdas_agency_code": "2966",
            "current_cdas_agency_name": "Lelefa Debt Collection",
            "agency_auto_detected": True,
        },
        "decision": "BOOK_NOW",
        "decision_message": "CDAS reports positive monthly deduction capacity, so booking is allowed now.",
        "next_possible_booking_date": "2026-09-01",
        "reported_active_monthly_deductions": 2171.0,
        "total_monthly_deductions": 2061.0,
        "own_monthly_deductions": 0.0,
        "competitor_monthly_deductions": 2061.0,
        "excluded_monthly_deductions": 110.0,
        "data_quality_issue_count": 1,
        "data_quality_issues": [conflict.copy()],
        "own_bookings": [],
        "opportunity": opportunity.copy(),
        "deductions": [opportunity.copy(), conflict.copy()],
    }


def _company() -> LoanCompany:
    return LoanCompany(
        name="Batlokoa Financial Services",
        registration_number="REG-2026-001",
        license_number="LIC-2026-001",
        phone="+266 5000 0000",
        email="info@example.co.ls",
        website="example.co.ls",
        address="Maseru",
        district="Maseru",
    )


def test_cdas_analysis_pdf_uses_tenant_document_design_system():
    content, reference = build_cdas_analysis_pdf(
        db=None,
        company=_company(),
        analysis=_analysis(),
        prepared_by_name="Mats'eliso Lelefa Luci",
        prepared_by_role="company_owner",
        client_name="Matekane Molefe",
        client_reference="EMP-4401",
        opportunity_id=uuid4(),
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 5000
    assert reference.startswith("CDAS-20260914-")
    assert cdas_report_filename("Matekane Molefe", reference).endswith(
        "-Matekane-Molefe.pdf"
    )


def test_cdas_complete_register_contains_every_structured_analysis_value():
    analysis = _analysis()
    flattened = dict(_flatten_structured_analysis(analysis))

    expected_paths = {
        "analysis.as_of",
        "analysis.booking_lead_months",
        "analysis.profile.name",
        "analysis.profile.surname",
        "analysis.profile.full_name",
        "analysis.profile.end_date",
        "analysis.capacity.status",
        "analysis.capacity.booking_allowed",
        "analysis.booking_term.calculation",
        "analysis.retirement_analysis.days_until_early_retirement",
        "analysis.retirement_analysis.days_until_compulsory_retirement",
        "analysis.application_context.agency_auto_detected",
        "analysis.decision",
        "analysis.decision_message",
        "analysis.next_possible_booking_date",
        "analysis.reported_active_monthly_deductions",
        "analysis.total_monthly_deductions",
        "analysis.own_monthly_deductions",
        "analysis.competitor_monthly_deductions",
        "analysis.excluded_monthly_deductions",
        "analysis.data_quality_issue_count",
        "analysis.data_quality_issues[0].booking_status",
        "analysis.opportunity.months_until_booking",
        "analysis.deductions[0].elapsed_months",
        "analysis.deductions[0].months_to_expiry",
        "analysis.deductions[0].scheduled_deduction_months",
        "analysis.deductions[0].booking_open_date",
        "analysis.deductions[0].booking_status",
        "analysis.deductions[1].data_quality_message",
    }

    assert expected_paths.issubset(flattened.keys())
    assert flattened["analysis.profile.end_date"] == "Not recorded"
    assert flattened["analysis.capacity.booking_allowed"] == "Yes"
    assert not any("raw_text" in path for path in flattened)


def test_cdas_analysis_pdf_handles_review_rows_without_expiry():
    analysis = _analysis()
    analysis["decision"] = "REVIEW_REQUIRED"
    analysis["decision_message"] = "Verify the incomplete CDAS row before monitoring."
    analysis["deductions"][1]["expiry_date"] = None
    analysis["deductions"][1]["data_quality_status"] = "MISSING_EXPIRY"
    analysis["deductions"][1]["data_quality_message"] = "CDAS did not provide an expiry month."
    analysis["deductions"][1]["booking_status"] = "DATA_INCOMPLETE"
    analysis["data_quality_issues"] = [analysis["deductions"][1]]

    company = LoanCompany(name="Tenant Company", phone="+266 5000 0000")
    content, reference = build_cdas_analysis_pdf(
        db=None,
        company=company,
        analysis=analysis,
        prepared_by_name="Company Owner",
        prepared_by_role="company_owner",
    )

    assert content.startswith(b"%PDF")
    assert reference.startswith("CDAS-")
