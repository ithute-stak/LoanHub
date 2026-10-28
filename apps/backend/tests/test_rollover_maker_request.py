"""Contracts for authenticated rollover reversal initiation and maker/checker binding."""
from pathlib import Path
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.postgresql import dialect
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest

ROOT = Path(__file__).resolve().parents[1]
ROUTER = (ROOT / "routers/loans.py").read_text()
MAKER = (ROOT / "services/rollover_reversal_request.py").read_text()
CHECKER = (ROOT / "services/rollover_checker_decision.py").read_text()


def test_request_comes_from_authenticated_maker_and_tenant():
    route = ROUTER.split("def submit_rollover_reversal_request(", 1)[1].split("\n\n\n", 1)[0]
    assert "maker_user_id=context.user.id" in route
    assert "company_id=context.company_id" in route
    assert "require_tenant_roles(context" in route
    assert '"posting_enabled": False' in MAKER


def test_checker_cannot_decide_without_maker_request():
    assert 'detail="Authenticated maker reversal request required"' in CHECKER
    assert "maker_id = request.maker_user_id" in CHECKER
    assert CHECKER.index("if request is None:") < CHECKER.index("verify_rollover_checker_identity(")
    assert "LoanRolloverReversalRequest.company_id == company_id" in CHECKER


def test_maker_request_is_unique_and_append_only():
    ddl = str(CreateTable(LoanRolloverReversalRequest.__table__).compile(dialect=dialect()))
    assert "uq_rollover_reversal_request_transfer" in ddl
    assert "uq_rollover_reversal_request_reference" in ddl
    migration = (ROOT / "alembic/versions/r8l1m2r6f477_rollover_reversal_request.py").read_text()
    assert "trg_rollover_reversal_request_immutable" in migration
    assert "prevent_rollover_transfer_mutation()" in migration


def test_financial_service_remains_disabled():
    fn = (ROOT / "services/rollover_compensation_posting.py").read_text().split(
        "def post_rollover_compensation(", 1
    )[1]
    assert fn.index("status_code=503") < fn.index("db.query(")
