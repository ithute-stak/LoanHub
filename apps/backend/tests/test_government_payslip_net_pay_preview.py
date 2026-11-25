"""No personal payslip input: preview is always unverified."""
from decimal import Decimal
from unittest.mock import patch

from PIL import Image

from services.government_payslip_net_pay_preview import preview_net_pay_amount
from services.government_payslip_amount_crop import AmountCropEvidence
from services.document_spatial_ocr import OCRWord


def word(text, left):
    return OCRWord(text, 95.0, left, 200, 40, 20, 1, 1, 1)


def test_net_pay_candidate_remains_review_only():
    image = Image.new("RGB", (900, 1000))
    with patch("services.government_payslip_net_pay_preview._safe_image", return_value=image):
        with patch("services.government_payslip_net_pay_preview.spatial_ocr",
                   return_value=(word("NET", 100), word("PAY", 148))):
            with patch("services.government_payslip_net_pay_preview.read_amount_crop",
                       return_value=AmountCropEvidence(
                           Decimal("2651.29"), ("2,651.29", "2,651.29"),
                           True, True, ("printed_amount_crop_requires_reviewer_confirmation",)
                       )):
                result = preview_net_pay_amount(b"test", "scan.png")
    assert result.candidate == Decimal("2651.29")
    assert result.status == "candidate_only"
    assert result.review_required


def test_missing_label_refuses_candidate_without_crop():
    image = Image.new("RGB", (900, 1000))
    with patch("services.government_payslip_net_pay_preview._safe_image", return_value=image):
        with patch("services.government_payslip_net_pay_preview.spatial_ocr", return_value=()):
            with patch("services.government_payslip_net_pay_preview.read_amount_crop") as crop:
                result = preview_net_pay_amount(b"test", "scan.png")
    assert result.candidate is None
    assert result.status == "manual_review"
    crop.assert_not_called()


def test_native_pdf_without_raster_stamp_remains_manual_review():
    with patch("services.government_payslip_net_pay_preview._pdf_pages",
               return_value=[("text", "synthetic payroll text")]):
        result = preview_net_pay_amount(b"test", "scan.pdf")
    assert result.candidate is None
    assert "net_pay_spatial_image_unavailable" in result.review_reasons
