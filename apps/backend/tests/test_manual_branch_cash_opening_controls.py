"""Daily branch cash funding and manual-opening policy safeguards."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from database.models.enums import OpeningSourceType, PaymentMethod, TreasuryDirection
from database.schemas.treasury import OpeningSourceCreate, TreasurySettingsUpdate
from services import treasury_service as treasury


class Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_criteria):
        return self

    def with_for_update(self):
        return self

    def group_by(self, *_args):
        return self

    def first(self):
        return self.result

    def scalar(self):
        return self.result

    def all(self):
        return self.result


class FundsDB:
    def __init__(self, ledger, manual_confirmed, opening, movements, cash_session=None):
        self.ledger = ledger
        self.manual_confirmed = manual_confirmed
        self.opening = opening
        self.movements = movements
        self.cash_session = cash_session
        self.queries = []

    def query(self, *columns):
        self.queries.append(columns)
        call = len(self.queries)
        result = {
            1: self.ledger,
            2: self.cash_session,
            3: SimpleNamespace(id=uuid4()) if self.manual_confirmed else None,
            4: self.opening,
            5: self.movements,
        }.get(call)
        return Query(result)


def make_ledger():
    return SimpleNamespace(
        id=uuid4(), company_id=uuid4(), branch_id=uuid4(),
        status=treasury.TreasuryDayStatus.OPEN,
    )


def test_manual_opening_is_the_default_and_carry_is_opt_in():
    assert TreasurySettingsUpdate().carry_previous_closing_enabled is False
    assert TreasurySettingsUpdate(carry_previous_closing_enabled=True).carry_previous_closing_enabled is True


def test_cash_float_can_be_explicitly_confirmed_at_zero():
    payload = OpeningSourceCreate(
        source_type=OpeningSourceType.CASH_FLOAT,
        payment_method=PaymentMethod.CASH,
        amount=Decimal("0.00"),
        description="Counted physical cash at branch opening",
    )
    assert payload.amount == Decimal("0.00")
    with pytest.raises(ValidationError):
        OpeningSourceCreate(
            source_type=OpeningSourceType.OWNER_CONTRIBUTION,
            amount=Decimal("0.00"), description="Invalid contribution",
        )
    with pytest.raises(ValidationError):
        OpeningSourceCreate(
            source_type=OpeningSourceType.CASH_FLOAT,
            amount=Decimal("-1"), description="Negative opening",
        )


def test_cash_outflow_requires_confirmed_manual_opening_even_if_other_inflows_exist():
    ledger = make_ledger()
    db = FundsDB(ledger, manual_confirmed=False, opening=Decimal("0"), movements=[])
    with pytest.raises(HTTPException, match="opening balance") as exc:
        treasury.assert_branch_outflow_funded(
            db, ledger=ledger, payment_method=PaymentMethod.CASH,
            amount=Decimal("20"), settings=SimpleNamespace(carry_previous_closing_enabled=False),
        )
    assert exc.value.status_code == 409
    assert len(db.queries) == 3


def test_cash_outflow_rejects_insufficient_funds_with_confirmed_opening():
    ledger = make_ledger()
    db = FundsDB(
        ledger, manual_confirmed=True, opening=Decimal("50.00"),
        movements=[(TreasuryDirection.MONEY_IN, Decimal("15.00")),
                   (TreasuryDirection.MONEY_OUT, Decimal("40.00"))],
    )
    with pytest.raises(HTTPException, match="Insufficient branch funds") as exc:
        treasury.assert_branch_outflow_funded(
            db, ledger=ledger, payment_method=PaymentMethod.CASH,
            amount=Decimal("25.01"), settings=SimpleNamespace(carry_previous_closing_enabled=False),
        )
    assert exc.value.status_code == 409


def test_cash_outflow_accepts_exact_available_funds():
    ledger = make_ledger()
    db = FundsDB(
        ledger, manual_confirmed=True, opening=Decimal("50.00"),
        movements=[(TreasuryDirection.MONEY_IN, Decimal("15.00")),
                   (TreasuryDirection.MONEY_OUT, Decimal("40.00"))],
    )
    available = treasury.assert_branch_outflow_funded(
        db, ledger=ledger, payment_method=PaymentMethod.CASH,
        amount=Decimal("25.00"), settings=SimpleNamespace(carry_previous_closing_enabled=False),
    )
    assert available == Decimal("25.00")


def test_prior_day_opening_is_not_automatically_carried_in_manual_mode(monkeypatch):
    # Existing historical sources are never removed or rewritten by a policy switch.
    from pathlib import Path
    source = Path(treasury.__file__).read_text(encoding="utf-8")
    section = source.split("def get_or_create_daily_ledger(")[1].split("def assert_ledger_writable(")[0]
    assert "if settings.carry_previous_closing_enabled:" in section
    assert "if (settings.carry_previous_closing_enabled" in section
    assert "if settings.carry_previous_closing_enabled:\n        _ensure_previous_closing_source" in section


def test_cash_loan_and_expense_paths_enforce_funding_before_posting():
    from pathlib import Path
    backend = Path(__file__).resolve().parents[1]
    loan = (backend / "services" / "loan_service.py").read_text(encoding="utf-8")
    treasury_code = (backend / "services" / "treasury_service.py").read_text(encoding="utf-8")
    cash_section = loan.split("def disburse_cash_loan(")[1].split("def record_borrower_request_fee(")[0]
    assert cash_section.index("assert_branch_outflow_funded(") < cash_section.index("payment = PaymentTransaction(")
    manual_section = treasury_code.split("def create_manual_entry(")[1].split("def approve_treasury_entry(")[0]
    approval_section = treasury_code.split("def approve_treasury_entry(")[1].split("def reject_treasury_entry(")[0]
    assert "assert_branch_outflow_funded(" in manual_section
    assert "assert_branch_outflow_funded(" in approval_section


def test_finance_desk_cash_session_is_projected_once_into_existing_treasury():
    from pathlib import Path
    backend = Path(__file__).resolve().parents[1]
    api = (backend / "routers" / "accounting.py").read_text(encoding="utf-8")
    service = (backend / "services" / "treasury_service.py").read_text(encoding="utf-8")
    open_section = api.split("def open_daily_cash_session(")[1].split('"/daily-cash/{session_id}/close"')[0]
    float_section = api.split("def top_up_daily_cash(")[1].split("class DailyCashClose(")[0]
    expense_section = api.split("def record_expense(")[1].split("def trial_balance_data(")[0]
    assert "sync_counted_cash_opening(" in open_section
    assert "sync_recorded_cash_float(" in float_section
    assert "sync_paid_accounting_expense(" in expense_section
    counted = service.split("def sync_counted_cash_opening(")[1].split("def sync_recorded_cash_float(")[0]
    float_projection = service.split("def sync_recorded_cash_float(")[1].split("def sync_paid_accounting_expense(")[0]
    expense_projection = service.split("def sync_paid_accounting_expense(")[1].split("def assert_branch_outflow_funded(")[0]
    assert "Cash movements were already posted" in counted
    assert "record_opening_source_accounting(" not in counted
    assert "record_opening_source_accounting(" not in float_projection
    assert "record_treasury_entry_accounting(" not in expense_projection
    assert "assert_branch_outflow_funded(" in expense_projection


def test_treasury_policy_migration_preserves_existing_opening_history():
    from pathlib import Path
    migration = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
        / "bc20261124001_manual_branch_opening_policy.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "dc20261122002"' in migration
    assert 'server_default=sa.text("false")' in migration
    assert "UPDATE branch_daily_ledgers" not in migration
    assert "DELETE FROM branch_opening_sources" not in migration


def test_closed_cash_session_blocks_outflow_even_with_available_cash():
    ledger = make_ledger()
    db = FundsDB(
        ledger, manual_confirmed=True, opening=Decimal("500"),
        movements=[], cash_session=SimpleNamespace(status="closed"),
    )
    with pytest.raises(HTTPException, match="cash session is closed") as exc:
        treasury.assert_branch_outflow_funded(
            db, ledger=ledger, payment_method=PaymentMethod.CASH,
            amount=Decimal("10"), settings=SimpleNamespace(carry_previous_closing_enabled=False),
        )
    assert exc.value.status_code == 409
    assert len(db.queries) == 2


def test_daily_cash_closing_serializes_against_outgoing_branch_cash():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "routers" / "accounting.py").read_text(encoding="utf-8")
    close = source.split("def close_daily_cash_session(")[1].split("def ", 1)[0]
    assert "BranchDailyLedger.company_id == record.company_id" in close
    assert "BranchDailyLedger.branch_id == record.branch_id" in close
    assert ".with_for_update().first()" in close
    assert close.index(".with_for_update().first()") < close.index("before = _cash_session_payload(record, db)")


def test_privileged_data_center_migration_gate_remains_fail_closed_after_treasury_revision():
    from pathlib import Path
    control = (Path(__file__).resolve().parents[1] / "scripts" / "data_center_pilot_control.py").read_text(encoding="utf-8")
    assert 'APPROVED_FORWARD_REVISIONS = {EXPECTED_REVISION, "bc20261124001"}' in control
    assert "len(versions) != 1 or versions[0] not in APPROVED_FORWARD_REVISIONS" in control
