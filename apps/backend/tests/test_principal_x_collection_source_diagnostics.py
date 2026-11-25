from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import TreasuryDirection

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus

from services.principal_x_collection_source_diagnostics import (
    inspect_principal_x_collection_sources,
)


class QueryDouble:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *args):
        return self

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class SessionDouble:
    def __init__(self, payments, cash, allocations, treasury):
        self.data = {
            "payment_transactions": payments,
            "cash_transactions": cash,
            "payment_allocations": allocations,
            "treasury_entries": treasury,
        }

    def query(self, model):
        return QueryDouble(self.data[model.__tablename__])


def test_linked_sources_are_not_double_counted():
    payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=payment_id, amount=Decimal('100'))],
        [SimpleNamespace(payment_id=payment_id, applied_amount=Decimal('100.00'))],
        [SimpleNamespace(payment_id=payment_id, amount=Decimal("100.00"))],
        [SimpleNamespace(payment_transaction_id=payment_id, amount=Decimal("100.00"), currency="LSL")],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_count == 1
    assert result.cash_link_count == 1
    assert result.allocation_count == 1
    assert result.treasury_count == 1
    assert result.orphan_cash_count == 0
    assert result.orphan_allocation_count == 0
    assert result.unlinked_treasury_count == 0
    assert result.complete is False


def test_unlinked_allocations_and_treasury_are_visible():
    db = SessionDouble(
        [], [],
        [SimpleNamespace(payment_id=uuid4())],
        [SimpleNamespace(payment_transaction_id=None)],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.orphan_allocation_count == 1
    assert result.unlinked_treasury_count == 1
    assert result.complete is False


def test_empty_sources_are_not_authoritative_proof():
    result = inspect_principal_x_collection_sources(
        SessionDouble([], [], [], []),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.complete is False


def test_invalid_tenant_is_rejected():
    with pytest.raises(ValueError):
        inspect_principal_x_collection_sources(
            SessionDouble([], [], [], []),
            company_id="wrong", loan_id=uuid4(),
        )


def test_treasury_link_to_another_payment_is_not_treated_as_verified():
    selected_payment_id = uuid4()
    unrelated_payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=selected_payment_id, amount=Decimal('100'))],
        [], [],
        [SimpleNamespace(payment_transaction_id=unrelated_payment_id)],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.unlinked_treasury_count == 1
    assert result.complete is False


def test_allocation_linked_to_another_loan_payment_is_flagged():
    selected_payment_id = uuid4()
    other_loan_payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=selected_payment_id, amount=Decimal('100'))],
        [],
        [SimpleNamespace(payment_id=other_loan_payment_id)],
        [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_count == 1
    assert result.orphan_allocation_count == 1
    assert result.complete is False


def test_cash_payment_without_cash_evidence_is_flagged():
    from database.models.enums import PaymentMethod

    payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=payment_id, payment_method=PaymentMethod.CASH)],
        [], [], [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.missing_cash_evidence_count == 1
    assert result.complete is False


def test_linked_cash_payment_does_not_raise_missing_evidence_flag():
    from database.models.enums import PaymentMethod

    payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=payment_id, amount=Decimal('100.00'), payment_method=PaymentMethod.CASH)],
        [SimpleNamespace(payment_id=payment_id, applied_amount=Decimal('100.00'))], [], [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.missing_cash_evidence_count == 0


def test_non_cash_payment_does_not_require_cash_transaction():
    from database.models.enums import PaymentMethod

    db = SessionDouble(
        [SimpleNamespace(id=uuid4(), payment_method=PaymentMethod.BANK)],
        [], [], [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.missing_cash_evidence_count == 0


def test_allocation_overage_across_installments_is_flagged_without_double_counting():
    payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
        [],
        [
            SimpleNamespace(payment_id=payment_id, amount=Decimal("70.00")),
            SimpleNamespace(payment_id=payment_id, amount=Decimal("30.02")),
        ],
        [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_count == 1
    assert result.allocation_count == 2
    assert result.overallocated_payment_count == 1
    assert result.complete is False


def test_partial_allocations_are_not_falsely_flagged():
    payment_id = uuid4()
    db = SessionDouble(
        [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
        [], [SimpleNamespace(payment_id=payment_id, amount=Decimal("80.00"))], [],
    )
    result = inspect_principal_x_collection_sources(
        db, company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.overallocated_payment_count == 0
    assert result.complete is False


@pytest.mark.parametrize("bad_amount", [
    Decimal("0"), Decimal("-1.00"), Decimal("NaN"), None,
])
def test_invalid_allocation_amount_is_a_readiness_blocker(bad_amount):
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [],
            [SimpleNamespace(payment_id=payment_id, amount=bad_amount)],
            [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.invalid_allocation_count == 1
    assert result.complete is False


def test_single_cent_overallocation_is_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [],
            [SimpleNamespace(payment_id=payment_id, amount=Decimal("100.01"))],
            [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.overallocated_payment_count == 1
    assert result.complete is False


def test_cash_applied_above_linked_payment_is_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [SimpleNamespace(payment_id=payment_id, applied_amount=Decimal("100.01"))],
            [], [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.cash_overapplied_count == 1
    assert result.complete is False


def test_cash_applied_below_linked_payment_is_not_assumed_invalid():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [SimpleNamespace(payment_id=payment_id, applied_amount=Decimal("80.00"))],
            [], [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.cash_overapplied_count == 0
    assert result.invalid_cash_amount_count == 0


@pytest.mark.parametrize("bad", [None, Decimal("NaN"), Decimal("-1")])
def test_invalid_cash_applied_amounts_are_flagged(bad):
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [SimpleNamespace(payment_id=payment_id, applied_amount=bad)],
            [], [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.invalid_cash_amount_count == 1
    assert result.complete is False


def test_missing_cash_applied_evidence_is_reported_not_crashed():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"))],
            [SimpleNamespace(payment_id=payment_id)], [], [],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.invalid_cash_amount_count == 1
    assert result.complete is False


def test_linked_posted_treasury_amount_mismatch_is_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"), currency="LSL")],
            [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id, amount=Decimal("100.01"),
                currency="LSL", approval_status="posted", is_voided=False,
            )],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_amount_mismatch_count == 1
    assert result.treasury_currency_mismatch_count == 0
    assert result.complete is False


def test_linked_treasury_wrong_currency_is_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"), currency="LSL")],
            [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id, amount=Decimal("100.00"),
                currency="USD", approval_status="posted", is_voided=False,
            )],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_amount_mismatch_count == 0
    assert result.treasury_currency_mismatch_count == 1


def test_voided_treasury_entry_is_not_compared_to_a_live_payment():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(id=payment_id, amount=Decimal("100.00"), currency="LSL")],
            [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id, amount=Decimal("200.00"),
                currency="USD", approval_status="posted", is_voided=True,
            )],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_amount_mismatch_count == 0
    assert result.treasury_currency_mismatch_count == 0


@pytest.mark.parametrize("treasury_currency,payment_currency", [
    (None, "LSL"), ("LSL", None), ("", "LSL"), ("LSL", ""),
])
def test_missing_linked_treasury_currency_is_a_reconciliation_blocker(
    treasury_currency, payment_currency,
):
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(
                id=payment_id, amount=Decimal("100.00"), currency=payment_currency,
            )],
            [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id,
                amount=Decimal("100.00"),
                currency=treasury_currency,
                approval_status="posted",
                is_voided=False,
            )],
        ),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_currency_mismatch_count == 1
    assert result.treasury_amount_mismatch_count == 0
    assert result.complete is False


@pytest.mark.parametrize("status,purpose,direction", [
    (PaymentStatus.PENDING, PaymentPurpose.LOAN_REPAYMENT, PaymentDirection.INBOUND),
    (PaymentStatus.FAILED, PaymentPurpose.LOAN_REPAYMENT, PaymentDirection.INBOUND),
    (PaymentStatus.SUCCEEDED, PaymentPurpose.REFUND, PaymentDirection.OUTBOUND),
    (PaymentStatus.SUCCEEDED, PaymentPurpose.LOAN_REPAYMENT, PaymentDirection.OUTBOUND),
])
def test_allocation_to_unverified_or_non_repayment_payment_is_flagged(
    status, purpose, direction,
):
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(
                id=payment_id, amount=Decimal("100.00"),
                status=status, purpose=purpose, direction=direction,
            )],
            [], [SimpleNamespace(payment_id=payment_id, amount=Decimal("80.00"))], [],
        ), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.nonfinal_allocation_payment_count == 1
    assert result.overallocated_payment_count == 0
    assert result.complete is False


def test_allocation_to_succeeded_inbound_loan_payment_is_not_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(
                id=payment_id, amount=Decimal("100.00"),
                status=PaymentStatus.SUCCEEDED,
                purpose=PaymentPurpose.LOAN_REPAYMENT,
                direction=PaymentDirection.INBOUND,
            )],
            [], [SimpleNamespace(payment_id=payment_id, amount=Decimal("80.00"))], [],
        ), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.nonfinal_allocation_payment_count == 0
    assert result.complete is False


def test_treasury_outbound_direction_for_inbound_payment_is_flagged():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(
                id=payment_id, amount=Decimal("100.00"), currency="LSL",
                direction=PaymentDirection.INBOUND,
            )], [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id, amount=Decimal("100.00"),
                currency="LSL", approval_status="posted", is_voided=False,
                direction=TreasuryDirection.MONEY_OUT,
            )],
        ), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_direction_mismatch_count == 1
    assert result.complete is False


def test_treasury_inbound_direction_matches_inbound_payment():
    payment_id = uuid4()
    result = inspect_principal_x_collection_sources(
        SessionDouble(
            [SimpleNamespace(
                id=payment_id, amount=Decimal("100.00"), currency="LSL",
                direction=PaymentDirection.INBOUND,
            )], [], [],
            [SimpleNamespace(
                payment_transaction_id=payment_id, amount=Decimal("100.00"),
                currency="LSL", approval_status="posted", is_voided=False,
                direction=TreasuryDirection.MONEY_IN,
            )],
        ), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.treasury_direction_mismatch_count == 0
