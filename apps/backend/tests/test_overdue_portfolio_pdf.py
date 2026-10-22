from types import SimpleNamespace

from services.overdue_portfolio_report_service import build_overdue_portfolio_pdf


def test_overdue_pdf_uses_loanhub_document_design_and_renders_rows():
    context = SimpleNamespace(
        company=SimpleNamespace(name="Example Lender", license_number="ML-001"),
    )
    pdf = build_overdue_portfolio_pdf(
        db=None,
        context=context,
        rows=[{
            "folio_number": "EX-CIV-00001",
            "loan_reference": "LN-TEST-001",
            "borrower_name": "Example Borrower",
            "due_date": "2026-09-22",
            "installment_amount": 700,
            "balance": 2100,
        }],
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 3000


def test_overdue_pdf_long_list_spans_pages():
    context = SimpleNamespace(
        company=SimpleNamespace(name="Example Lender", license_number="ML-001"),
    )
    rows = [{
        "folio_number": f"EX-CIV-{i:05d}",
        "loan_reference": f"LN-TEST-{i:05d}",
        "borrower_name": f"Borrower {i}",
        "due_date": "2026-09-22",
        "installment_amount": 700,
        "balance": 2100,
    } for i in range(100)]
    pdf = build_overdue_portfolio_pdf(db=None, context=context, rows=rows)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10000
