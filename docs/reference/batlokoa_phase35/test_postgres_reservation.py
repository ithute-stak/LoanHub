"""Mock-only tests. Does NOT certify PostgreSQL concurrency or RLS."""
from decimal import Decimal
from uuid import UUID
import pytest
from postgres_reservation import reserve_collection_intent, ReservationStatus

COMPANY = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
LOAN = UUID("00000000-0000-4000-8000-000000000001")
BORROWER = UUID("00000000-0000-4000-8000-000000000002")
KEY = "collection_request_1234567"
FP = "a" * 64

def args():
    return dict(company_id=COMPANY, loan_id=LOAN, borrower_id=BORROWER,
                idempotency_key=KEY, request_fingerprint=FP, amount=Decimal("100.00"))

def test_created_repeat_conflict():
    row_id = UUID("00000000-0000-4000-8000-000000000003")
    class Result:
        def __init__(self, inserted):
            self.inserted = inserted
        def scalar_one_or_none(self):
            return row_id if self.inserted else None
        def mappings(self):
            return self
        def one_or_none(self):
            return dict(id=row_id, loan_id=LOAN, borrower_id=BORROWER,
                request_fingerprint=FP, amount=Decimal("100.00"), currency="LSL")
    class DB:
        def __init__(self, inserted):
            self.inserted = inserted
        def execute(self, sql, params):
            return Result(self.inserted if "INSERT" in str(sql) else False)
    assert reserve_collection_intent(DB(True), **args()).status == ReservationStatus.CREATED
    assert reserve_collection_intent(DB(False), **args()).status == ReservationStatus.SAME_REQUEST
    changed = {**args(), "request_fingerprint": "b"*64}
    assert reserve_collection_intent(DB(False), **changed).status == ReservationStatus.CONFLICT

def test_bad_key_does_not_query_db():
    class NoDatabase:
        def execute(self, *a, **kw):
            raise AssertionError("Invalid key may not query database")
    with pytest.raises(ValueError):
        reserve_collection_intent(NoDatabase(), **{**args(), "idempotency_key":"bad"})
