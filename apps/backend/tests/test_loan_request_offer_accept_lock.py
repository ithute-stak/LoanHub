from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, joinedload

from database.models.loan_request import LoanRequest


def test_offer_accept_lock_targets_only_loan_request_table() -> None:
    """Joined borrower data must not be included in the PostgreSQL row lock."""
    session = Session()
    try:
        query = (
            session.query(LoanRequest)
            .options(joinedload(LoanRequest.borrower))
            .filter(LoanRequest.id == uuid4())
            .with_for_update(of=LoanRequest)
        )
        sql = str(query.statement.compile(dialect=postgresql.dialect()))
    finally:
        session.close()

    assert "LEFT OUTER JOIN borrowers" in sql
    assert "FOR UPDATE OF loan_requests" in sql
    assert "FOR UPDATE OF borrowers" not in sql
