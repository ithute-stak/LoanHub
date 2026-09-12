from pathlib import Path


def test_payment_slip_route_uses_direct_renderer():
    source = Path("routers/loans.py").read_text()
    start = source.index('@router.get("/{loan_id}/payment-slips/{receipt_id}.pdf")')
    end = source.index('@router.get("/by-reference/{loan_reference}"', start)
    route = source[start:end]

    assert "generate_payment_receipt_pdf" in route
    assert "read_file_bytes" not in route
    assert "db.get(ManagedFile" not in route
    assert "status_code=410" not in route


def test_receipt_service_exports_direct_renderer():
    source = Path("services/receipt_service.py").read_text()
    assert "def generate_payment_receipt_pdf(" in source
    assert "return _pdf_bytes(db, receipt, payment, resolved_loan)" in source
