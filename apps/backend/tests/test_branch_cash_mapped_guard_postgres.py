"""Real mapped LoanHub treasury funding guard under PostgreSQL concurrency.

Uses the application's actual BranchDailyLedger, BranchOpeningSource and
TreasuryEntry SQLAlchemy models and the actual funding guard. The tables are
cloned into a disposable, isolated schema without external foreign-key targets;
no production financial records are touched.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
import os
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from database.models.company_operating_system import CompanyOperatingRecord
from database.models.enums import (
    OpeningSourceType, PaymentMethod, TreasuryDayStatus, TreasuryDirection,
    TreasuryEntryApprovalStatus, TreasuryEntryType,
)
from database.models.treasury import BranchDailyLedger, BranchOpeningSource, TreasuryEntry
from services.treasury_service import assert_branch_outflow_funded


def test_actual_mapped_branch_funding_guard_prevents_double_disbursement():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("Disposable PostgreSQL integration DSN not configured")
    engine = create_engine(dsn, pool_size=3, max_overflow=0)
    schema = "cash_guard_mapped_" + uuid4().hex[:14]
    company, branch = uuid4(), uuid4()
    day = date(2026, 11, 25)
    ledger_id = uuid4()
    barrier = Barrier(2)
    settings = SimpleNamespace(
        carry_previous_closing_enabled=False,
        enforce_branch_cash_controls_enabled=True,
    )
    tables = [
        BranchDailyLedger.__table__,
        BranchOpeningSource.__table__,
        TreasuryEntry.__table__,
        CompanyOperatingRecord.__table__,
    ]
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            for table in tables:
                # Clone the actual model DDL but remove links to unrelated
                # company/user/loan tables in this self-contained test schema.
                conn.execute(CreateTable(table, include_foreign_key_constraints=[]))
            conn.execute(text("""
                INSERT INTO branch_daily_ledgers
                (id, company_id, branch_id, business_date, status,
                 opening_balance, total_money_in, total_money_out,
                 expected_closing_balance, variance_amount,
                 entry_count, pending_entry_count)
                VALUES (:ledger, :company, :branch, :day, 'open',
                        100, 0, 0, 100, 0, 0, 0)
            """), dict(ledger=ledger_id, company=company, branch=branch, day=day))
            conn.execute(text("""
                INSERT INTO branch_opening_sources
                (id, company_id, branch_id, daily_ledger_id, source_type,
                 payment_method, amount, description, source_reference,
                 is_system_generated, is_confirmed, is_voided)
                VALUES (:id, :company, :branch, :ledger, 'cash_float',
                        'cash', 100, 'Manual counted cash', 'OPEN-MAPPED-001',
                        false, true, false)
            """), dict(id=uuid4(), company=company, branch=branch, ledger=ledger_id))

        def worker() -> bool:
            barrier.wait(timeout=12)
            with Session(engine) as db:
                with db.begin():
                    db.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    ledger = db.get(BranchDailyLedger, ledger_id)
                    try:
                        assert_branch_outflow_funded(
                            db, ledger=ledger, payment_method=PaymentMethod.CASH,
                            amount=Decimal("80.00"), settings=settings,
                        )
                    except HTTPException as exc:
                        assert exc.status_code == 409
                        assert "Insufficient branch funds" in str(exc.detail)
                        return False
                    entry = TreasuryEntry(
                        company_id=company, branch_id=branch,
                        daily_ledger_id=ledger_id,
                        direction=TreasuryDirection.MONEY_OUT,
                        entry_type=TreasuryEntryType.LOAN_DISBURSEMENT,
                        payment_method=PaymentMethod.CASH,
                        approval_status=TreasuryEntryApprovalStatus.POSTED,
                        requires_approval=False, amount=Decimal("80.00"),
                        currency="LSL", occurred_at=datetime.now(timezone.utc),
                        description="Disposable mapped concurrent payout",
                        idempotency_key=str(uuid4()),
                    )
                    db.add(entry)
                    db.flush()
                    return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            outcomes = [f.result(timeout=30) for f in futures]
        assert sorted(outcomes) == [False, True]
        with engine.connect() as conn:
            conn.execute(text(f'SET search_path TO "{schema}"'))
            actual = conn.execute(text("""
                SELECT count(*), COALESCE(sum(amount), 0)
                FROM treasury_entries
                WHERE daily_ledger_id = :ledger AND approval_status = 'posted'
            """), {"ledger": ledger_id}).one()
            assert actual == (1, Decimal("80.00"))
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            engine.dispose()
