from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from routers.folio_book import _integrity
from services.folio_identity_integration import stamp_pdf_folio


ROOT = Path(__file__).resolve().parents[2]


def _loan(folio: str | None, company: str | None, group: str | None, sequence: int | None, loan_id: str):
    return SimpleNamespace(
        id=loan_id,
        folio_number=folio,
        folio_company_code=company,
        folio_group_code=group,
        folio_sequence=sequence,
    )


def test_integrity_reports_independent_sequence_books_and_next_numbers():
    result = _integrity([
        _loan("BFS-LDF-00001", "BFS", "LDF", 1, "l1"),
        _loan("BFS-LDF-00002", "BFS", "LDF", 2, "l2"),
        _loan("BFS-LMPS-00001", "BFS", "LMPS", 1, "m1"),
        _loan("BFS-LMPS-00002", "BFS", "LMPS", 2, "m2"),
    ])
    assert result["healthy"] is True
    groups = {item["group_code"]: item for item in result["groups"]}
    assert groups["LDF"]["next_folio"] == "BFS-LDF-00003"
    assert groups["LMPS"]["next_folio"] == "BFS-LMPS-00003"
    assert groups["LDF"]["gap_count"] == 0
    assert groups["LMPS"]["gap_count"] == 0


def test_integrity_surfaces_gap_missing_malformed_and_duplicate_folios():
    result = _integrity([
        _loan("BFS-LDF-00001", "BFS", "LDF", 1, "a"),
        _loan("BFS-LDF-00001", "BFS", "LDF", 1, "b"),
        _loan("BFS-LDF-00003", "BFS", "LDF", 3, "c"),
        _loan("WRONG", "BFS", "LMPS", 1, "d"),
        _loan(None, None, None, None, "e"),
    ])
    assert result["healthy"] is False
    assert result["gap_count"] == 1
    assert result["missing_folio_count"] == 1
    assert result["malformed_folio_count"] == 1
    assert result["duplicate_folio_count"] == 1
    assert result["duplicate_folios"]["BFS-LDF-00001"] == ["a", "b"]


def test_pdf_folio_stamp_is_extractable_and_does_not_drop_original_content():
    source = BytesIO()
    pdf = canvas.Canvas(source)
    pdf.drawString(72, 720, "ORIGINAL LOAN DOCUMENT")
    pdf.save()
    stamped = stamp_pdf_folio(source.getvalue(), "BFS-LMPS-00042")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(stamped)).pages)
    assert "ORIGINAL LOAN DOCUMENT" in text
    assert "FOLIO BFS-LMPS-00042" in text


def test_runtime_integration_is_installed_before_api_router_composition():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    install = source.index("install_folio_identity_integration()")
    api_router = source.index("from api.v1.router import api_router")
    assert install < api_router


def test_folio_identity_propagates_to_contract_documents_receipts_and_collections():
    source = (ROOT / "backend" / "services" / "folio_identity_integration.py").read_text(encoding="utf-8")
    assert 'enriched["folio_number"]' in source
    assert "_ContractCanvas._draw_branding" in source
    assert "loan_document_service._document_context" in source
    assert "receipt_service._pdf_bytes" in source
    assert 'payload["folio_number"]' in source


def test_folio_book_api_and_frontend_surface_are_registered():
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    folio_router = (ROOT / "backend" / "routers" / "folio_book.py").read_text(encoding="utf-8")
    report_router = (ROOT / "backend" / "routers" / "folio_book_reports.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "folio-book" / "page.tsx").read_text(encoding="utf-8")
    loans_layout = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "layout.tsx").read_text(encoding="utf-8")

    assert "folio_book.router" in api_router
    assert "folio_book_reports.router" in api_router
    assert '@router.get("/integrity")' in folio_router
    assert '@router.get("/export.csv")' in folio_router
    assert '@router.get("/export.pdf")' in report_router
    assert "Loan Folio Book" in frontend
    assert "BFS-LMPS-00001" in frontend
    assert "/company/folio-book" in loans_layout
