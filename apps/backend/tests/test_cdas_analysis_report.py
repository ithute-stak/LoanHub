from uuid import uuid4

from database.models.company import LoanCompany
from services.cdas_analysis_report_service import (
    build_cdas_analysis_pdf,
    cdas_report_filename,
)


def _analysis() -> dict:
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
        "data_quality_issues": [
            {
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
                "booking_open_date": None,
            }
        ],
        "own_bookings": [],
        "opportunity": {
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
            "booking_open_date": "2028-04-01",
        },
        "deductions": [
            {
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
                "booking_open_date": "2028-04-01",
            },
            {
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
                "booking_open_date": None,
            },
        ],
    }


def test_cdas_analysis_pdf_uses_tenant_document_design_system():
    company = LoanCompany(
        name="Batlokoa Financial Services",
        registration_number="REG-2026-001",
        license_number="LIC-2026-001",
        phone="+266 5000 0000",
        email="info@example.co.ls",
        website="example.co.ls",
        address="Maseru",
        district="Maseru",
    )

    content, reference = build_cdas_analysis_pdf(
        db=None,
        company=company,
        analysis=_analysis(),
        prepared_by_name="Mats'eliso Lelefa Luci",
        prepared_by_role="company_owner",
        client_name="Matekane Molefe",
        client_reference="EMP-4401",
        opportunity_id=uuid4(),
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 3000
    assert reference.startswith("CDAS-20260914-")
    assert cdas_report_filename("Matekane Molefe", reference).endswith(
        "-Matekane-Molefe.pdf"
    )


def test_cdas_analysis_pdf_handles_review_rows_without_expiry():
    analysis = _analysis()
    analysis["decision"] = "REVIEW_REQUIRED"
    analysis["decision_message"] = "Verify the incomplete CDAS row before monitoring."
    analysis["deductions"][1]["expiry_date"] = None
    analysis["deductions"][1]["data_quality_status"] = "MISSING_EXPIRY"
    analysis["deductions"][1]["data_quality_message"] = "CDAS did not provide an expiry month."
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
