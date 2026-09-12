from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.schemas.origination import (
    BankAccountInput,
    FinancialProfileUpdate,
    OriginationApplicationCreate,
    OriginationPolicyUpdate,
)
from services.loan_service import calculate_micro_loan_totals
from services.origination_service import json_safe


def test_micro_loan_method_reference_example():
    monthly, total, breakdown = calculate_micro_loan_totals(
        Decimal("1000.00"), Decimal("20"), 3, Decimal("0")
    )
    assert monthly == Decimal("464.00")
    assert total == Decimal("1392.00")
    assert [step["component_amount"] for step in breakdown["steps"]] == ["600.00", "360.00", "432.00"]


def test_policy_rejects_invalid_age_range():
    with pytest.raises(ValidationError):
        OriginationPolicyUpdate(min_age=70, max_age=50)


def test_top_up_policy_defaults_to_seventy_five_percent_with_owner_exception():
    policy = OriginationPolicyUpdate()
    assert policy.allow_top_up is True
    assert policy.top_up_min_paid_percent == Decimal("75")
    assert policy.top_up_owner_exception_enabled is True
    assert policy.top_up_settle_existing_balance is True


def test_card_payload_rejects_full_pan():
    with pytest.raises(ValidationError):
        BankAccountInput(
            account_holder="Borrower Name",
            bank_name="Example Bank",
            account_number="12345678",
            masked_card_number="4111111111111111",
        )


def test_card_payload_accepts_masked_value_and_token():
    payload = BankAccountInput(
        account_holder="Borrower Name",
        bank_name="Example Bank",
        account_number="12345678",
        masked_card_number="**** 4832",
        tokenized_card_provider="Hosted Provider",
        tokenized_card_reference="tok_safe_reference",
    )
    assert payload.masked_card_number == "**** 4832"


def test_json_safe_converts_uuid_date_and_decimal_for_jsonb():
    identifier = uuid4()
    payload = json_safe({
        "id": identifier,
        "date": date(2026, 7, 21),
        "amount": Decimal("1000.00"),
        "nested": [Decimal("20.5")],
    })
    assert payload == {
        "id": str(identifier),
        "date": "2026-07-21",
        "amount": "1000.00",
        "nested": ["20.5"],
    }


def test_application_requires_manual_installment_due_dates():
    first = date.today() + timedelta(days=40)
    dates = [first, first + timedelta(days=35), first + timedelta(days=70)]
    payload = OriginationApplicationCreate(
        borrower_id=uuid4(),
        requested_amount=Decimal("1000"),
        term_count=3,
        installment_due_dates=dates,
    )
    assert payload.installment_due_dates == dates

    with pytest.raises(ValidationError):
        OriginationApplicationCreate(
            borrower_id=uuid4(),
            requested_amount=Decimal("1000"),
            term_count=3,
            installment_due_dates=dates[:2],
        )

    with pytest.raises(ValidationError):
        OriginationApplicationCreate(
            borrower_id=uuid4(),
            requested_amount=Decimal("1000"),
            term_count=3,
            installment_due_dates=[dates[0], dates[2], dates[1]],
        )


def test_shared_profile_accepts_multiple_banks_and_rejects_two_salary_accounts():
    first = BankAccountInput(
        account_holder="Borrower Name",
        bank_name="FNB Lesotho",
        account_number="12345678",
        salary_account=True,
    )
    second = BankAccountInput(
        account_holder="Borrower Name",
        bank_name="Standard Lesotho Bank",
        account_number="87654321",
    )
    payload = FinancialProfileUpdate(
        kyc={},
        employment={},
        bank_accounts=[first, second],
    )
    assert len(payload.bank_accounts) == 2

    with pytest.raises(ValidationError):
        FinancialProfileUpdate(
            kyc={},
            employment={},
            bank_accounts=[
                first,
                second.model_copy(update={"salary_account": True}),
            ],
        )
