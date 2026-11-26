"""Pure synthetic tests for spatial stamp preview; no personal files."""
from datetime import date
from unittest.mock import patch

from PIL import Image

from services.document_spatial_ocr import OCRWord
from services.government_payslip_stamp_preview import preview_payslip_stamp

TODAY = date(2026, 11, 24)


def _word(text, x, y, block=1):
    return OCRWord(text, 95.0, x, y, 150, 24, block, 1, 1)


def test_stamp_date_inside_region_is_preview_only():
    img = Image.new("RGB", (1200, 1400), "white")
    words = [_word("STAMP", 650, 900, 1), _word("23 Nov 2026", 650, 940, 2)]
    with patch("services.government_payslip_stamp_preview._images", return_value=(img,)):
        with patch("services.government_payslip_stamp_preview.spatial_ocr", return_value=tuple(words)):
            result = preview_payslip_stamp(b"fake", "scan.pdf", assessed_at=TODAY)
    assert result.status == "valid_date"
    assert result.detected_stamp_date == "2026-11-23"
    assert result.manual_review_required
    assert "stamp_authenticity_unverified" in result.review_reasons


def test_dates_outside_stamp_region_are_ignored():
    img = Image.new("RGB", (1200, 1400), "white")
    words = [_word("23 Nov 2026", 50, 100, 1), _word("STAMP", 650, 900, 2)]
    with patch("services.government_payslip_stamp_preview._images", return_value=(img,)):
        with patch("services.government_payslip_stamp_preview.spatial_ocr", return_value=tuple(words)):
            result = preview_payslip_stamp(b"fake", "scan.pdf", assessed_at=TODAY)
    assert result.status == "missing"
    assert result.detected_stamp_date is None


def test_native_pdf_without_spatial_scan_stays_unverified():
    with patch("services.government_payslip_stamp_preview._images", return_value=()):
        result = preview_payslip_stamp(b"fake", "scan.pdf", assessed_at=TODAY)
    assert result.status == "manual_review"
    assert result.manual_review_required


def test_expired_stamp_is_not_allowed():
    img = Image.new("RGB", (1200, 1400), "white")
    words = [_word("STAMP", 650, 900, 1), _word("23 Aug 2026", 650, 940, 2)]
    with patch("services.government_payslip_stamp_preview._images", return_value=(img,)):
        with patch("services.government_payslip_stamp_preview.spatial_ocr", return_value=tuple(words)):
            result = preview_payslip_stamp(b"fake", "scan.pdf", assessed_at=TODAY)
    assert result.status == "expired"
    assert result.manual_review_required
