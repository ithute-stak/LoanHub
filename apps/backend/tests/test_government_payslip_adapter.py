"""Synthetic payslip data only; no real employee details in source control."""
from datetime import date
from decimal import Decimal

import pytest

from services.document_intelligence_foundation import StampStatus
from services.government_payslip_adapter import (
    GovernmentPayslipError,
    assess_payslip_stamp,
    parse_government_payslip,
)

SAMPLE = """STAFF PAYSLIP
Staff No: GOV-00001
Employee Name: EXAMPLE EMPLOYEE
Employee Reference: 12345
Ministry: EXAMPLE MINISTRY
Department: EXAMPLE DEPARTMENT
Designation: Example Officer
Pay Period: November 2026
Earnings
Basic Salary    8826.00
Deductions
PAYE    847.41
Pension    441.30
Insurance    231.00
Other One    20.00
Other Two    30.00
Other Three    91.00
Loan Repayment    4514.00
Total Earnings 8826.00
Total Deductions 6174.71
Net Pay 2651.29
"""


def test_extracts_employee_and_all_monetary_rows():
    result = parse_government_payslip(SAMPLE)
    assert result.fields["employee_number"] == "GOV-00001"
    assert result.fields["employee_name"] == "EXAMPLE EMPLOYEE"
    assert result.pay_period == "November 2026"
    assert result.printed_gross == Decimal("8826.00")
    assert result.printed_net == Decimal("2651.29")
    assert len(result.earnings) == 1
    assert len(result.deductions) == 7
    assert result.totals_reconciled
    assert result.review_required
    assert "issuer_and_stamp_unverified" in result.review_reasons


def test_wrong_total_is_not_accepted():
    result = parse_government_payslip(SAMPLE.replace("Net Pay 2651.29", "Net Pay 2651.30"))
    assert not result.totals_reconciled
    assert "totals_mismatch" in result.review_reasons


def test_missing_financial_row_refuses_parsing():
    with pytest.raises(GovernmentPayslipError):
        parse_government_payslip(SAMPLE.replace("Loan Repayment    4514.00", "Loan Repayment    NOT_READABLE"))


def test_missing_printed_total_refuses_parsing():
    with pytest.raises(GovernmentPayslipError, match="totals missing"):
        parse_government_payslip(SAMPLE.replace("Total Deductions 6174.71", ""))


def test_missing_identity_requires_review_not_invention():
    result = parse_government_payslip(SAMPLE.replace("Staff No: GOV-00001", ""))
    assert "employee_number" not in result.fields
    assert "employee_identity_incomplete" in result.review_reasons


def test_stamp_date_policy_is_kept_separate_from_payroll_dates():
    today = date(2026, 11, 24)
    assert assess_payslip_stamp([], assessed_at=today).status == StampStatus.MISSING
    assert assess_payslip_stamp([date(2026, 8, 23)], assessed_at=today).status == StampStatus.EXPIRED
    assert assess_payslip_stamp([date(2026, 8, 24)], assessed_at=today).status == StampStatus.VALID_DATE
    assert assess_payslip_stamp([date(2026, 11, 25)], assessed_at=today).status == StampStatus.FUTURE_DATE
    assert assess_payslip_stamp([date(2026, 10, 1), date(2026, 11, 1)], assessed_at=today).status == StampStatus.AMBIGUOUS
