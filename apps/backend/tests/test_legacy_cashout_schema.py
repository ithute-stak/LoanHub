from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from database.schemas.legacy_cashout import LegacyCashoutCaptureCreate, normalise_legacy_capture_status


def _payload(**overrides):
    value = {
        "folio_number": "F-018",
        "loan_date": date.today() - timedelta(days=1),
        "first_names": "Mpho",
        "surname": "Mokoena",
        "identity_number": "123456789",
        "cell_phone": "59001111",
        "bank_name": "FNB",
        "bank_account_holder": "Mpho Mokoena",
        "bank_account_number": "6123456789",
        "amount_taken": Decimal("1000.00"),
        "total_repayable": Decimal("1200.00"),
        "amount_paid": Decimal("200.00"),
        "installment_count": 4,
        "installment_amount": Decimal("300.00"),
    }
    value.update(overrides)
    return value


def test_digits_only_identity_is_a_lesotho_national_id_without_expiry():
    capture = LegacyCashoutCaptureCreate(**_payload(identity_number=" 1234567890 "))
    assert capture.identity_type == "national_id"
    assert capture.identity_number == "1234567890"
    assert capture.passport_expiry_date is None


def test_passport_requires_expiry_date():
    with pytest.raises(ValidationError, match="Passport expiry date is required"):
        LegacyCashoutCaptureCreate(**_payload(identity_number="A1234567"))


def test_passport_with_letters_accepts_an_expiry_date():
    capture = LegacyCashoutCaptureCreate(
        **_payload(
            identity_number="a1234567",
            passport_expiry_date=date.today() + timedelta(days=365),
        )
    )
    assert capture.identity_type == "passport"
    assert capture.identity_number == "A1234567"


def test_national_id_rejects_an_expiry_date():
    with pytest.raises(ValidationError, match="Lesotho national IDs do not have an expiry date"):
        LegacyCashoutCaptureCreate(
            **_payload(passport_expiry_date=date.today() + timedelta(days=365))
        )


def test_legacy_amount_paid_cannot_exceed_recorded_total_repayable():
    with pytest.raises(ValidationError, match="Amount paid cannot exceed"):
        LegacyCashoutCaptureCreate(**_payload(amount_paid=Decimal("1200.01")))


def test_draft_capture_requires_only_folio_loan_date_and_banking_details():
    capture = LegacyCashoutCaptureCreate(
        folio_number="F-019",
        loan_date=date.today() - timedelta(days=1),
        bank_name="FNB",
        bank_account_holder="Historic borrower",
        bank_account_number="6012345678",
    )
    assert capture.identity_type is None
    assert capture.amount_taken == Decimal("0")
    assert capture.bank_account_number == "6012345678"


def test_converted_legacy_status_is_presented_as_posted():
    assert normalise_legacy_capture_status("converted") == "posted"
    assert normalise_legacy_capture_status("posted") == "posted"



def test_legacy_capture_applies_standard_branch_and_code():
    capture = LegacyCashoutCaptureCreate(
        **_payload(
            bank_name="fnb",
            bank_account_number="6123-456-789",
            bank_branch_name="Historic branch",
            bank_branch_code="999999",
        )
    )
    assert capture.bank_name == "FNB"
    assert capture.bank_account_number == "6123456789"
    assert capture.bank_branch_name == "Maseru Central"
    assert capture.bank_branch_code == "280061"


def test_legacy_capture_rejects_unsupported_bank():
    with pytest.raises(ValidationError, match="Bank must be one of FNB, PB, STD or NB"):
        LegacyCashoutCaptureCreate(**_payload(bank_name="Example Bank"))


def test_legacy_capture_rejects_wrong_account_prefix():
    with pytest.raises(ValidationError, match="FNB account number must start with 6"):
        LegacyCashoutCaptureCreate(**_payload(bank_name="FNB", bank_account_number="9012345678"))
