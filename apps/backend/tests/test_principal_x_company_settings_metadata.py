"""Metadata registration tests for isolated Principal x% company settings."""
from database.base import Base
from database.models import CompanyPaymentModelSettings


def test_company_payment_settings_registered_for_alembic():
    table = Base.metadata.tables["company_payment_model_settings"]
    assert table is CompanyPaymentModelSettings.__table__
    assert table.c.company_id.nullable is False
    assert table.c.default_model.server_default.arg == "existing"
    assert table.c.allow_new_loans.server_default.arg == "false"
    assert table.c.enable_live_collections.server_default.arg == "false"


def test_company_settings_is_separate_from_calculator_tables():
    table = CompanyPaymentModelSettings.__table__
    assert table.name == "company_payment_model_settings"
    assert "loan_companies" in {
        fk.column.table.name for fk in table.c.company_id.foreign_keys
    }
