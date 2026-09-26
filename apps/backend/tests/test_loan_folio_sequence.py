from pathlib import Path

from services.loan_folio import company_folio_code, employer_folio_code


ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "apps" / "backend" / "database" / "models" / "client_loan_company.py"
SCHEMA = ROOT / "apps" / "backend" / "database" / "schemas" / "loan.py"
MIGRATION = ROOT / "apps" / "backend" / "alembic" / "versions" / "f0l10a5e0001_add_loan_folio_sequence.py"


def test_batlokoa_and_ldf_folio_codes_match_sequence_book_format():
    assert company_folio_code("Batlokoa Financial Service") == "BFS"
    assert company_folio_code("Batlokoa Financial Services (Pty) Ltd") == "BFS"
    assert employer_folio_code(group_name="Lesotho Defence Force") == "LDF"
    assert employer_folio_code(group_code="LDF", group_name="Lesotho Defence Force") == "LDF"


def test_other_companies_and_employers_get_deterministic_codes():
    assert company_folio_code("Lelefa Debt Collectors (Pty) Ltd") == "LDC"
    assert company_folio_code("Khanya Resources") == "KR"
    assert employer_folio_code(group_name="Lesotho Mounted Police Service") == "LMPS"
    assert employer_folio_code() == "GEN"


def test_loan_model_owns_immutable_folio_fields_and_allocator():
    source = MODEL.read_text(encoding="utf-8")
    assert 'folio_number = Column(String(40), nullable=False, index=True)' in source
    assert 'folio_company_code = Column(String(8), nullable=False)' in source
    assert 'folio_group_code = Column(String(8), nullable=False, index=True)' in source
    assert 'folio_sequence = Column(Integer, nullable=False)' in source
    assert 'event.listen(ClientCompanyLoan, "before_insert", assign_loan_folio)' in source
    assert 'UniqueConstraint(\n            "company_id",\n            "folio_group_code",\n            "folio_sequence"' in source


def test_allocator_is_concurrency_safe_and_formats_five_digit_sequence():
    source = (ROOT / "apps" / "backend" / "services" / "loan_folio.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in source
    assert "MAX(folio_sequence)" in source
    assert ':05d' in source
    assert 'if getattr(target, "folio_number", None):' in source


def test_loan_api_exposes_folio_and_migration_backfills_existing_loans():
    schema = SCHEMA.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "folio_number: str" in schema
    assert "folio_group_code: str" in schema
    assert "ORDER BY l.company_id, l.created_at, l.id" in migration
    assert "folio_number = :folio" in migration
    assert 'op.alter_column("client_company_loan", "folio_number"' in migration
