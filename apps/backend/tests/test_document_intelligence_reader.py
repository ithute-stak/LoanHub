"""No client documents, OCR binaries or network needed for unit tests."""
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image

from services.document_intelligence_foundation import DocumentKind
from services.document_intelligence_reader import (
    DocumentReadError,
    _read_image,
    _safe_image,
    read_document,
)


def _image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 40), "white").save(output, format="PNG")
    return output.getvalue()


def test_rejects_unsupported_and_mismatched_files():
    with pytest.raises(DocumentReadError):
        read_document(b"not a PDF", filename="statement.pdf")
    with pytest.raises(DocumentReadError):
        read_document(_image_bytes(), filename="statement.txt")
    with pytest.raises(DocumentReadError):
        read_document(b"", filename="statement.png")


def test_rejects_excessively_large_upload_before_processing():
    with pytest.raises(DocumentReadError, match="upload limit"):
        read_document(b"x" * (12 * 1024 * 1024 + 1), filename="scan.png")


def test_image_reads_all_rotations_and_selects_strongest_candidate():
    calls = iter([
        ("garbled text", 27.0),
        ("Bank Opening Balance Closing Balance Transaction Account Number", 95.0),
        ("wrong orientation", 23.0),
        ("partial", 35.0),
    ])
    with patch(
        "services.document_intelligence_reader._ocr_tsv", side_effect=lambda image: next(calls)
    ) as ocr:
        result = read_document(_image_bytes(), filename="scan.png")
    assert ocr.call_count == 4
    assert result.pages[0].orientation_correction == 90
    assert result.classification == DocumentKind.BANK_STATEMENT
    assert not result.review_required


def test_unknown_or_low_confidence_requires_review():
    with patch("services.document_intelligence_reader._ocr_tsv", return_value=("hello", 22.0)):
        result = read_document(_image_bytes(), filename="scan.png")
    assert result.review_required
    assert result.classification == DocumentKind.UNKNOWN


def test_image_rejects_pixel_bomb_dimensions():
    img = Image.new("RGB", (6000, 10), "white")
    output = BytesIO()
    img.save(output, format="PNG")
    with pytest.raises(DocumentReadError, match="dimension"):
        _safe_image(output.getvalue())


def test_pdf_with_native_text_does_not_need_ocr():
    # PDF text extraction is mocked here; real PDF fixtures remain an integration test.
    class FakePage:
        def extract_text(self):
            return "Opening Balance Closing Balance Transaction Debit Credit " * 3

    class FakePdf:
        is_encrypted = False
        pages = [FakePage()]

    with patch("services.document_intelligence_reader.PdfReader", return_value=FakePdf()):
        result = read_document(b"%PDF-test", filename="test.pdf")
    assert result.classification == DocumentKind.BANK_STATEMENT
    assert not result.review_required


def test_scanned_pdf_routes_to_image_ocr():
    with patch("services.document_intelligence_reader._pdf_pages", return_value=[("image", Image.new("RGB", (80, 40)))]):
        with patch(
            "services.document_intelligence_reader._ocr_tsv",
            return_value=("Staff Payslip Earnings Deductions Net Pay " * 3, 95.0),
        ):
            result = read_document(b"%PDF-scanned", filename="scan.pdf")
    assert result.classification == DocumentKind.GOVERNMENT_PAYSLIP
