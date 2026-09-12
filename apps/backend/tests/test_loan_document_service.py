from datetime import date, datetime, timezone

from services.loan_document_service import (
    render_loan_information_pdf,
    render_payment_history_pdf,
    render_repayment_schedule_pdf,
)


def sample_context():
    return {
        "generated_at": datetime.now(timezone.utc),
        "company": {"name": "Example Lender", "license_number": "ML-001"},
        "branch": {"name": "Head Office"},
        "borrower": {
            "name": "Borrower Example",
            "user_id": "user-1",
            "national_id": "123456789012",
            "passport_number": None,
            "phone": "+266 50000000",
            "email": "borrower@example.com",
            "address": "Maseru",
            "employment_status": "Employed",
            "employer_name": "Employer",
        },
        "loan": {
            "reference": "LB-20260722-000001-EXAMPLE",
            "status": "Active",
            "channel": "Internal Client Offer",
            "principal": 1000,
            "interest_rate": 20,
            "processing_fee": 0,
            "total_repayable": 1200,
            "repayment_type": "Monthly",
            "repayment_period": 2,
            "installment_amount": 600,
            "amount_paid": 600,
            "balance": 600,
            "approved_at": datetime.now(timezone.utc),
            "disbursed_at": datetime.now(timezone.utc),
            "first_payment_due": date(2026, 8, 22),
            "maturity_date": date(2026, 9, 22),
            "risk_level": "Low",
            "is_overdue": False,
            "is_top_up": False,
            "top_up_settlement_amount": 0,
            "top_up_cash_amount": 0,
        },
        "schedule": [
            {
                "number": 1,
                "due_date": date(2026, 8, 22),
                "principal": 500,
                "interest": 100,
                "fees": 0,
                "total": 600,
                "paid": 600,
                "status": "Paid",
                "paid_at": datetime.now(timezone.utc),
            },
            {
                "number": 2,
                "due_date": date(2026, 9, 22),
                "principal": 500,
                "interest": 100,
                "fees": 0,
                "total": 600,
                "paid": 0,
                "status": "Pending",
                "paid_at": None,
            },
        ],
        "payments": [
            {
                "id": "payment-1",
                "date": datetime.now(timezone.utc),
                "purpose": "Loan Repayment",
                "direction": "Inbound",
                "method": "Cash",
                "amount": 600,
                "reference": "PAY-001",
                "status": "Succeeded",
                "receipt_number": "RCP-001",
                "verification_code": "VERIFY001",
            }
        ],
    }


def test_fastapi_loan_documents_are_valid_pdfs():
    context = sample_context()
    documents = [
        render_loan_information_pdf(context),
        render_repayment_schedule_pdf(context),
        render_payment_history_pdf(context),
    ]
    for content in documents:
        assert content.startswith(b"%PDF-")
        assert len(content) > 1_000
