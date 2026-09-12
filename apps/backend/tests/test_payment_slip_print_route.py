from pathlib import Path


def test_payment_slip_print_route_never_uses_managed_file_storage():
    source = Path("routers/loans.py").read_text()
    start = source.index("def payment_slip_pdf_by_payment")
    end = source.index("@router.get(\"/{loan_id}/payment-slips/{receipt_id}.pdf\")", start)
    route = source[start:end]
    assert "generate_payment_receipt_pdf" in route
    assert "ensure_pdf=False" in route
    assert "read_file_bytes" not in route
    assert "status_code=410" not in route


def test_receipt_service_can_skip_persisted_pdf():
    source = Path("services/receipt_service.py").read_text()
    assert "ensure_pdf: bool = True" in source
    assert "if ensure_pdf and not _receipt_pdf_available" in source
    assert "if ensure_pdf:" in source
