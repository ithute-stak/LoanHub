"""Targeted OCR tests: all numeric readings are synthetic."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from PIL import Image

from services.document_intelligence_reader import DocumentReadError
from services.government_payslip_amount_crop import read_amount_crop


def image():
    return Image.new("RGB", (800, 900), "white")


def test_sharpened_crop_recovers_comma_formatted_amount():
    with patch("services.government_payslip_amount_crop._run_amount_ocr", side_effect=["2,651.29", "2,651.29"]) as ocr:
        result = read_amount_crop(image(), (500, 100, 750, 160))
    assert result.candidate == Decimal("2651.29")
    assert result.mode_agreement
    assert result.review_required
    assert ocr.call_count == 2


def test_conflicting_digits_do_not_create_a_false_amount():
    with patch("services.government_payslip_amount_crop._run_amount_ocr", side_effect=["2,651.29", "2,651.28"]):
        result = read_amount_crop(image(), (500, 100, 750, 160))
    assert result.candidate is None
    assert "amount_crop_ocr_disagreement" in result.review_reasons


def test_one_ocr_failure_does_not_count_as_agreement():
    with patch("services.government_payslip_amount_crop._run_amount_ocr", side_effect=["", "2,651.29"]):
        result = read_amount_crop(image(), (500, 100, 750, 160))
    assert result.candidate is None


def test_ambiguous_multi_amounts_not_accepted():
    with patch("services.government_payslip_amount_crop._run_amount_ocr", side_effect=["2,651.29 847.41", "2,651.29"]):
        result = read_amount_crop(image(), (500, 100, 750, 160))
    assert result.candidate is None


def test_box_must_be_inside_image():
    with pytest.raises(ValueError, match="bounds"):
        read_amount_crop(image(), (500, 100, 900, 160))


def test_oversized_crop_rejected():
    with pytest.raises(DocumentReadError, match="dimensions"):
        read_amount_crop(Image.new("RGB", (3000, 3000)), (0, 0, 3000, 3000))
