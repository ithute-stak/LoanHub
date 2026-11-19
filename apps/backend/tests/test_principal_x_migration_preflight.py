from types import SimpleNamespace

from database.base import Base
from database.models import ClientCompanyLoan, CompanyPaymentModelSettings, LoanPaymentModelAssignmentRecord
from scripts.check_principal_x_migration_preflight import verify_migration_metadata


def test_registered_schema_with_single_head_is_eligible_for_review():
    assert verify_migration_metadata(["known-head"], Base.metadata) == []


def test_multiple_heads_block_migration():
    errors = verify_migration_metadata(["head-a", "head-b"], Base.metadata)
    assert any("exactly one" in error for error in errors)


def test_no_head_blocks_migration():
    assert verify_migration_metadata([], Base.metadata)


def test_missing_tables_block_migration():
    errors = verify_migration_metadata(["head"], SimpleNamespace(tables={}))
    assert any("Missing ORM tables" in error for error in errors)
