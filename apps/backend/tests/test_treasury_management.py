from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from database.models.enums import (
    PaymentMethod,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.schemas.treasury import TreasuryEntryCreate, TreasurySettingsUpdate
from services.treasury_service import (
    PAYMENT_METHOD_LABELS,
    _active_entries,
    _channel_totals,
    method_totals_for_entries,
    payment_method_options,
    resolve_payment_branch_id,
    validate_manual_proof,
)


def test_only_cash_and_gateway_are_available_for_new_postings():
    expected = {"lelefapaygate", "cash"}
    assert {row["value"].value for row in payment_method_options()} == expected
    assert PAYMENT_METHOD_LABELS[PaymentMethod.LELEFAPAYGATE] == "LelefaPayGate"
    # Historical labels remain available for rendering immutable old records.
    assert PAYMENT_METHOD_LABELS[PaymentMethod.GOLINK] == "goLink"
    assert PAYMENT_METHOD_LABELS[PaymentMethod.ECOCASH_MERCHANT] == "EcoCash Merchant"


def test_real_world_daily_cycle_defaults_and_validation():
    settings = TreasurySettingsUpdate()
    assert settings.auto_open_time.isoformat() == "00:01:00"
    assert settings.auto_submit_time.isoformat() == "16:30:00"

    with pytest.raises(ValidationError):
        TreasurySettingsUpdate(auto_open_time="17:00", auto_submit_time="16:30")


def test_non_cash_proof_can_be_required_by_company_policy():
    settings = SimpleNamespace(require_proof_for_non_cash=True)
    with pytest.raises(HTTPException) as caught:
        validate_manual_proof(settings, PaymentMethod.BANK, None, None)
    assert caught.value.status_code == 422

    validate_manual_proof(settings, PaymentMethod.BANK, "BANK-REF-100", None)
    validate_manual_proof(settings, PaymentMethod.MPESA_AGENT, None, "documents/proof.png")
    validate_manual_proof(settings, PaymentMethod.CASH, None, None)


def test_expense_entry_requires_an_expense_category():
    with pytest.raises(ValidationError):
        TreasuryEntryCreate(
            branch_id=uuid4(),
            direction=TreasuryDirection.MONEY_OUT,
            entry_type=TreasuryEntryType.EXPENSE,
            payment_method=PaymentMethod.CASH,
            amount=Decimal("125.00"),
            description="Office stationery",
        )


def test_selected_channel_totals_keep_money_in_and_out_separate():
    entries = [
        SimpleNamespace(
            is_voided=False,
            payment_method=PaymentMethod.CASH,
            direction=TreasuryDirection.MONEY_IN,
            amount=Decimal("500.00"),
        ),
        SimpleNamespace(
            is_voided=False,
            payment_method=PaymentMethod.BANK,
            direction=TreasuryDirection.MONEY_IN,
            amount=Decimal("300.00"),
        ),
        SimpleNamespace(
            is_voided=False,
            payment_method=PaymentMethod.CASH,
            direction=TreasuryDirection.MONEY_OUT,
            amount=Decimal("125.00"),
        ),
        SimpleNamespace(
            is_voided=True,
            payment_method=PaymentMethod.CASH,
            direction=TreasuryDirection.MONEY_IN,
            amount=Decimal("999.00"),
        ),
    ]
    raw = _channel_totals(entries)
    assert raw["cash"]["money_in"] == "500.00"
    assert raw["cash"]["money_out"] == "125.00"
    assert raw["cash"]["net"] == "375.00"
    assert raw["bank"]["net"] == "300.00"

    rows = {row["method"]: row for row in method_totals_for_entries(entries)}
    assert rows[PaymentMethod.CASH]["entry_count"] == 2
    assert rows[PaymentMethod.BANK]["money_in"] == Decimal("300.00")
    assert rows[PaymentMethod.CDAS]["net"] == Decimal("0.00")


def test_channel_position_carries_confirmed_opening_balance_by_method():
    entries = [
        SimpleNamespace(
            is_voided=False,
            payment_method=PaymentMethod.BANK,
            direction=TreasuryDirection.MONEY_IN,
            amount=Decimal("25.00"),
        ),
        SimpleNamespace(
            is_voided=False,
            payment_method=PaymentMethod.CASH,
            direction=TreasuryDirection.MONEY_OUT,
            amount=Decimal("10.00"),
        ),
    ]
    sources = [
        SimpleNamespace(
            is_voided=False,
            is_confirmed=True,
            payment_method=PaymentMethod.BANK,
            amount=Decimal("100.00"),
        ),
        SimpleNamespace(
            is_voided=False,
            is_confirmed=True,
            payment_method=PaymentMethod.CASH,
            amount=Decimal("50.00"),
        ),
    ]

    rows = {row["method"]: row for row in method_totals_for_entries(entries, sources)}
    assert rows[PaymentMethod.BANK]["opening_balance"] == Decimal("100.00")
    assert rows[PaymentMethod.BANK]["closing_balance"] == Decimal("125.00")
    assert rows[PaymentMethod.CASH]["opening_balance"] == Decimal("50.00")
    assert rows[PaymentMethod.CASH]["closing_balance"] == Decimal("40.00")


def test_payment_branch_resolution_prefers_explicit_then_linked_operational_branch():
    explicit = uuid4()
    loan_branch = uuid4()
    cash_branch = uuid4()
    account_branch = uuid4()
    payment = SimpleNamespace(
        company_id=None,
        loan=SimpleNamespace(branch_id=loan_branch),
        cash_transaction=SimpleNamespace(branch_id=cash_branch),
        company_borrower_account=SimpleNamespace(branch_id=account_branch),
    )

    assert resolve_payment_branch_id(None, payment, explicit) == explicit
    assert resolve_payment_branch_id(None, payment) == loan_branch
    payment.loan = None
    assert resolve_payment_branch_id(None, payment) == cash_branch
    payment.cash_transaction = None
    assert resolve_payment_branch_id(None, payment) == account_branch


def test_pending_expense_does_not_affect_posted_totals():
    posted = SimpleNamespace(
        is_voided=False,
        approval_status=TreasuryEntryApprovalStatus.POSTED,
    )
    approved = SimpleNamespace(
        is_voided=False,
        approval_status=TreasuryEntryApprovalStatus.APPROVED,
    )
    pending = SimpleNamespace(
        is_voided=False,
        approval_status=TreasuryEntryApprovalStatus.PENDING,
    )
    rejected = SimpleNamespace(
        is_voided=False,
        approval_status=TreasuryEntryApprovalStatus.REJECTED,
    )
    assert _active_entries([posted, approved, pending, rejected]) == [posted, approved]


def test_platform_fee_and_billing_schemas_accept_verified_non_cash_methods():
    from database.models.enums import BillingCycle
    from database.schemas.billing import MarketplaceUnlockCreate, SubscriptionCheckoutCreate
    from database.schemas.cash import CashBorrowerRequestFeeCreate
    from database.schemas.finance import ClaimCashSettlementCreate

    subscription = SubscriptionCheckoutCreate(
        plan_id=uuid4(),
        billing_cycle=BillingCycle.MONTHLY,
        payment_method=PaymentMethod.BANK,
        proof_reference="BANK-SUB-100",
    )
    unlock = MarketplaceUnlockCreate(
        payment_method=PaymentMethod.MPESA_MERCHANT,
        proof_reference="MPESA-UNLOCK-100",
    )
    request_fee = CashBorrowerRequestFeeCreate(
        payment_method=PaymentMethod.ECOCASH_WALLET,
        proof_reference="ECO-FEE-100",
    )
    claim = ClaimCashSettlementCreate(
        payment_method=PaymentMethod.CDAS,
        proof_url="proofs/claim-cdas-100.pdf",
    )

    assert subscription.payment_method == PaymentMethod.BANK
    assert unlock.payment_method == PaymentMethod.MPESA_MERCHANT
    assert request_fee.payment_method == PaymentMethod.ECOCASH_WALLET
    assert claim.payment_method == PaymentMethod.CDAS
