"""Execute scoped accounting parity queries against a real in-memory SQL database.

This validates row filtering rather than only compiling SQL expressions.
PostgreSQL-specific RLS is not covered by this SQLite test.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Column, Date, ForeignKey, Integer, MetaData, Numeric, String, Table, create_engine, text
from sqlalchemy.orm import Session

from services import accounting_scoped_parity


def test_query_executes_with_tenant_posting_period_and_branch_isolation(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "journal_entries", metadata,
        Column("id", String(36), primary_key=True),
        Column("scope_key", String(80), nullable=False),
        Column("status", String(20), nullable=False),
        Column("entry_date", Date, nullable=False),
        Column("branch_id", String(36)),
    )
    Table(
        "journal_lines", metadata,
        Column("id", Integer, primary_key=True),
        Column("journal_entry_id", String(36), ForeignKey("journal_entries.id")),
        Column("account_id", String(36), nullable=False),
        Column("debit", Numeric(20, 2), nullable=False),
        Column("credit", Numeric(20, 2), nullable=False),
    )
    metadata.create_all(engine)
    branch_a = "00000000-0000-0000-0000-0000000000aa"
    branch_b = "00000000-0000-0000-0000-0000000000bb"
    a1 = "00000000-0000-0000-0000-000000000011"
    a2 = "00000000-0000-0000-0000-000000000022"
    cases = [
        (1, "company:A", "posted", "2026-01-10", branch_a, 100),
        (2, "company:B", "posted", "2026-01-10", branch_a, 200),
        (3, "company:A", "draft", "2026-01-10", branch_a, 300),
        (4, "company:A", "posted", "2026-02-10", branch_a, 400),
        (5, "company:A", "posted", "2026-01-10", branch_b, 500),
    ]
    with engine.begin() as conn:
        for ident, scope, status, posted, branch, cents in cases:
            eid = f"00000000-0000-0000-0000-{ident:012d}"
            conn.execute(text(
                "INSERT INTO journal_entries (id,scope_key,status,entry_date,branch_id) "
                "VALUES (:id,:scope,:status,:posted,:branch)"
            ), {"id": UUID(eid).hex, "scope": scope, "status": status, "posted": posted, "branch": UUID(branch).hex})
            for idx, (account_id, debit, credit) in enumerate(
                [(a1, Decimal(cents) / 100, 0), (a2, 0, Decimal(cents) / 100)]
            ):
                conn.execute(text(
                    "INSERT INTO journal_lines (id,journal_entry_id,account_id,debit,credit) "
                    "VALUES (:line,:entry,:account,:debit,:credit)"
                ), {
                    "line": ident * 2 + idx, "entry": UUID(eid).hex, "account": UUID(account_id).hex,
                    "debit": debit, "credit": credit,
                })

    received = []
    def parity(rows):
        received.extend(rows)
        return {"native_cpp_matched": False, "python_trial_balance": "100|100\\n"}

    monkeypatch.setattr(accounting_scoped_parity, "advisory_trial_balance", parity)
    with Session(engine) as db:
        report = accounting_scoped_parity.scoped_trial_balance_parity(
            db, scope_key="company:A", from_date=date(2026, 1, 1),
            to_date=date(2026, 1, 31), branch_id=UUID(branch_a),
        )
        assert report["journal_line_count"] == 2
        assert report["account_count"] == 2
        assert sorted((d, c) for _, d, c in received) == [
            (Decimal("0.00"), Decimal("1.00")),
            (Decimal("1.00"), Decimal("0.00")),
        ]
        assert report["authoritative"] is False
        assert not db.dirty and not db.new
    engine.dispose()
