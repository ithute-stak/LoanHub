from pathlib import Path

from services.folio_book_service import _sequence_books
from services.loan_folio import company_folio_code, employer_folio_code


ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "apps" / "backend" / "database" / "models" / "client_loan_company.py"
SCHEMA = ROOT / "apps" / "backend" / "database" / "schemas" / "loan.py"
MIGRATION = ROOT / "apps" / "backend" / "alembic" / "versions" / "f0l10a5e0001_add_loan_folio_sequence.py"
FRONTEND_TYPE = ROOT / "apps" / "frontend" / "types" / "loan.ts"
FOLIO_SERVICE = ROOT / "apps" / "backend" / "services" / "folio_book_service.py"
FOLIO_ROUTER = ROOT / "apps" / "backend" / "routers" / "folio_book.py"
FOLIO_EXTENSION = ROOT / "apps" / "backend" / "services" / "folio_contract_extension.py"
FOLIO_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "folio-book" / "page.tsx"
FOLIO_API = ROOT / "apps" / "frontend" / "api" / "folioBook.ts"
BORROWER_LOANS = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "borrower" / "loans" / "page.tsx"
LEGACY_REGISTER_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "legacy-cashout-register" / "page.tsx"


def test_batlokoa_and_ldf_folio_codes_match_sequence_book_format():
    assert company_folio_code("Batlokoa Financial Service") == "BFS"
    assert company_folio_code("Batlokoa Financial Services (Pty) Ltd") == "BFS"
    assert employer_folio_code(group_name="Lesotho Defence Force") == "LDF"
    assert employer_folio_code(group_code="LDF", group_name="Lesotho Defence Force") == "LDF"


def test_other_companies_and_employers_get_deterministic_codes():
    assert company_folio_code("Lelefa Debt Collectors (Pty) Ltd") == "LDC"
    assert company_folio_code("Khanya Resources") == "KR"
    assert employer_folio_code(group_name="Lesotho Mounted Police Service") == "LMPS"
    assert employer_folio_code(group_code="LMPS", group_name="Lesotho Mounted Police Service") == "LMPS"
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


def test_loan_api_and_frontend_expose_folio_and_migration_backfills_existing_loans():
    schema = SCHEMA.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    frontend_type = FRONTEND_TYPE.read_text(encoding="utf-8")
    assert "folio_number: str" in schema
    assert "folio_group_code: str" in schema
    assert "folio_number: string;" in frontend_type
    assert "folio_group_code: string;" in frontend_type
    assert "ORDER BY l.company_id, l.created_at, l.id" in migration
    assert "folio_number = :folio" in migration
    assert 'down_revision = "a0o4q6s8t802"' in migration
    assert 'op.alter_column("client_company_loan", "folio_number"' in migration


def test_sequence_book_never_recycles_a_gap_when_calculating_next_folio():
    rows = [
        {
            "folio_company_code": "BFS",
            "folio_group_code": "LMPS",
            "folio_sequence": 1,
            "employer_group_name": "Lesotho Mounted Police Service",
        },
        {
            "folio_company_code": "BFS",
            "folio_group_code": "LMPS",
            "folio_sequence": 3,
            "employer_group_name": "Lesotho Mounted Police Service",
        },
    ]
    books, total_gaps = _sequence_books(rows)
    assert total_gaps == 1
    assert books[0]["gaps"] == [2]
    assert books[0]["last_sequence"] == 3
    assert books[0]["next_sequence"] == 4
    assert books[0]["next_folio_number"] == "BFS-LMPS-00004"


def test_folio_book_has_integrity_controls_search_and_csv_export():
    service = FOLIO_SERVICE.read_text(encoding="utf-8")
    router = FOLIO_ROUTER.read_text(encoding="utf-8")
    assert "duplicate_folio" in service
    assert "duplicate_sequence" in service
    assert "component_mismatch" in service
    assert "invalid_format" in service
    assert "gap_count" in service
    assert "MAX(sequence)+1" in service
    assert '"folio_number"' in service
    assert '"borrower_identity"' in service
    assert '@router.get("")' in router
    assert '@router.get("/export.csv")' in router
    assert "LoanHub-Folio-Book.csv" in router


def test_folio_is_propagated_to_contracts_loan_pdfs_receipts_and_collections():
    extension = FOLIO_EXTENSION.read_text(encoding="utf-8")
    assert 'terms["folio_number"]' in extension
    assert '("Folio number", folio)' in extension
    assert 'identity = f"FOLIO {folio}"' in extension
    assert '_loan_documents.generate_repayment_schedule_pdf = generate_repayment_schedule_pdf' in extension
    assert '_loan_documents.generate_payment_history_pdf = generate_payment_history_pdf' in extension
    assert '_receipts._pdf_bytes = _receipt_pdf_bytes' in extension
    assert 'payload["folio_number"] = folio or None' in extension
    assert 'payload["loan_reference"] = f"{folio} | {loan_reference}"' in extension


def test_frontend_has_searchable_folio_book_and_borrower_folio_history():
    page = FOLIO_PAGE.read_text(encoding="utf-8")
    api = FOLIO_API.read_text(encoding="utf-8")
    borrower = BORROWER_LOANS.read_text(encoding="utf-8")
    legacy = LEGACY_REGISTER_PAGE.read_text(encoding="utf-8")
    assert "Loan Folio Book" in page
    assert "Permanent loan sequence book" in page
    assert "next_folio_number" in page
    assert "Search folio, borrower, ID, loan" in page
    assert "Export CSV" in page
    assert 'api.get<FolioBookPayload>("/folio-book"' in api
    assert '"/folio-book/export.csv"' in api
    assert "loan.folio_number" in borrower
    assert "selected.folio_number" in borrower
    assert "/company/folio-book" in legacy
