from types import SimpleNamespace

from services.contract_service import _bank_account_number, _contract_pdf, _money


def _sample_terms() -> dict:
    return {
        "company": {
            "name": "Example Lender (Pty) Ltd",
            "registration_number": "LS-2026-001",
            "license_number": "ML-001",
            "address": "Maseru",
            "district": "Maseru",
            "phone": "+266 2200 0000",
            "email": "loans@example.co.ls",
        },
        "branch": {"name": "Maseru Main"},
        "legal_basis": "Applicable Lesotho lending law.",
        "borrower": {
            "name": "Test Borrower",
            "identity_type": "National ID",
            "identity_number": "123456789012",
            "date_of_birth": "1990-01-01",
            "physical_address": "Maseru",
            "phone": "+266 5800 0000",
            "email": "borrower@example.com",
            "employment_status": "Employed",
            "employer_name": "Example Employer",
        },
        "bank_account": {
            "account_holder": "Test Borrower",
            "bank_name": "Example Bank",
            "branch_name": "Maseru",
            "branch_code": "001",
            "account_type": "savings",
            "currency": "LSL",
            "account_number_encrypted": None,
            "account_number_last4": "1234",
            "verification_status": "verified",
        },
        "application_reference": "APP-001",
        "application_purpose": "Personal use",
        "loan_product_name": "Personal Micro Loan",
        "loan_reference": "LN-001",
        "agreement_date": "2026-07-22",
        "is_top_up": False,
        "principal_amount": "1000.00",
        "interest_rate": "10.00",
        "interest_rate_basis": "Approved loan rate",
        "total_interest": "100.00",
        "processing_fee": "20.00",
        "total_fees": "20.00",
        "schedule_fees": "20.00",
        "total_cost_of_credit": "120.00",
        "tax_amount": "0.00",
        "total_repayable": "1120.00",
        "installment_amount": "1120.00",
        "repayment_period": 1,
        "repayment_type": "Once Off",
        "calculation_method": "flat",
        "first_payment_due": "2026-08-22",
        "preferred_payment_day": 22,
        "maturity_date": "2026-08-22",
        "schedule": [{
            "number": 1,
            "due_date": "2026-08-22",
            "principal": "1000.00",
            "interest": "100.00",
            "fee": "20.00",
            "amount": "1120.00",
        }],
        "schedule_total": "1120.00",
        "payment_method": "Cash or approved electronic payment",
        "security_type": "Unsecured",
        "insurance_status": "Not included",
        "partial_payment_rule": "Payments are allocated to the oldest outstanding instalment first.",
        "advance_payment_rule": "The borrower may make early payments.",
        "complaints_email": "loans@example.co.ls",
        "complaints_phone": "+266 2200 0000",
        "generated_at": "2026-07-22T09:30:00+00:00",
    }


def test_contract_pdf_is_generated_with_branding_and_multiple_sections():
    contract = SimpleNamespace(
        terms_snapshot=_sample_terms(),
        contract_number="LHC-TEST-001",
        version=1,
        status="awaiting_signatures",
        contract_hash="a" * 64,
        company_signer_user_id=None,
        borrower_signature_name=None,
        borrower_signed_at=None,
        borrower_signature_method=None,
        company_signed_at=None,
        company_signature_method=None,
        witness_name=None,
        locked_at=None,
    )

    content = _contract_pdf(None, contract)

    assert content.startswith(b"%PDF-")
    assert len(content) > 55_000


def test_contract_money_uses_lesotho_currency():
    assert _money("1234.5") == "LSL 1,234.50"


def test_contract_bank_account_falls_back_to_masked_number():
    assert _bank_account_number({"account_number_last4": "1234"}) == "****1234"
