from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import TreasuryEntryType
from services.principal_x_manual_adjustment_review import review_manual_adjustments


def evidence():
    company, loan, branch, entry_id = uuid4(), uuid4(), uuid4(), uuid4()
    entry = SimpleNamespace(
        id=entry_id, company_id=company, loan_id=loan, branch_id=branch,
        payment_transaction_id=None, approval_status="posted", is_voided=False,
        entry_type=TreasuryEntryType.ADJUSTMENT, amount=Decimal("100.00"), currency="LSL",
    )
    journal = SimpleNamespace(
        company_id=company, branch_id=branch, reference_type="treasury_entry",
        reference_id=str(entry_id), status="posted", voided_at=None,
        total_debit=Decimal("100.00"), total_credit=Decimal("100.00"),
        lines=[SimpleNamespace(debit=Decimal("100"), credit=Decimal("0")),
               SimpleNamespace(debit=Decimal("0"), credit=Decimal("100"))],
    )
    return entry, journal, dict(company_id=company, loan_id=loan)


@pytest.mark.parametrize("problem,missing,inconsistent", [
    ("none", 0, 0), ("missing", 1, 0), ("duplicate", 0, 1),
    ("unbalanced", 0, 1), ("wrong_amount", 0, 1), ("branch", 0, 1),
    ("draft", 0, 1), ("currency", 0, 1), ("invalid_line", 0, 1),
    ("header", 0, 1), ("voided_journal", 0, 1),
])
def test_manual_treasury_journal_review(problem, missing, inconsistent):
    entry, journal, scope = evidence()
    journals = [journal]
    if problem == "missing":
        journals = []
    elif problem == "duplicate":
        journals.append(SimpleNamespace(**vars(journal)))
    elif problem == "unbalanced":
        journal.lines[1].credit = Decimal("99")
    elif problem == "wrong_amount":
        entry.amount = Decimal("101")
    elif problem == "branch":
        journal.branch_id = uuid4()
    elif problem == "draft":
        journal.status = "draft"
    elif problem == "currency":
        entry.currency = "USD"
    elif problem == "invalid_line":
        journal.lines[0].credit = Decimal("1")
    elif problem == "header":
        journal.total_debit = Decimal("99")
    elif problem == "voided_journal":
        journal.voided_at = object()
    result = review_manual_adjustments(treasury=[entry], journals=journals, **scope)
    assert result.treasury_count == 1
    assert result.missing_journal_count == missing
    assert result.inconsistent_journal_count == inconsistent
    assert result.complete is False


@pytest.mark.parametrize("kind", ["voided", "pending", "linked_payment"])
def test_nonqualifying_treasury_is_not_counted_as_manual_posting(kind):
    entry, journal, scope = evidence()
    if kind == "voided":
        entry.is_voided = True
    elif kind == "pending":
        entry.approval_status = "pending"
    else:
        entry.payment_transaction_id = uuid4()
    result = review_manual_adjustments(treasury=[entry], journals=[], **scope)
    assert result.treasury_count == 0
    assert result.complete is False


def test_write_off_is_reported_separately_from_cash():
    entry, journal, scope = evidence()
    journal.reference_type = "loan_write_off"
    journal.reference_id = str(scope["loan_id"])
    result = review_manual_adjustments(treasury=[], journals=[journal], **scope)
    assert result.write_off_journal_count == 1
    assert result.treasury_count == 0
    assert result.complete is False


@pytest.mark.parametrize("kind", ["journal", "treasury"])
def test_cross_company_records_rejected(kind):
    entry, journal, scope = evidence()
    (journal if kind == "journal" else entry).company_id = uuid4()
    with pytest.raises(ValueError):
        review_manual_adjustments(treasury=[entry], journals=[journal], **scope)
