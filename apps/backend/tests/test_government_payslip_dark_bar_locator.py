"""Synthetic dark-bar locator regression tests; no personal payslips."""
import pytest
from PIL import Image, ImageDraw

from services.document_spatial_ocr import OCRWord
from services.government_payslip_amount_locator import AmountCellLocationError
from services.government_payslip_dark_bar_locator import locate_dark_bar_net_pay_cell


def sample_image(*, two_bars=True):
    image = Image.new("RGB", (1698, 2400), "white")
    paint = ImageDraw.Draw(image)
    paint.rectangle((225, 1275, 718, 1322), fill="black")
    if two_bars:
        paint.rectangle((225, 1351, 718, 1396), fill="black")
    return image


def heading(*, confidence=96):
    return OCRWord("Earnings", confidence, 240, 955, 90, 21, 1, 1, 1)


def test_dark_bar_locator_returns_second_bar_adjacent_amount_cell():
    result = locate_dark_bar_net_pay_cell(sample_image(), (heading(),))
    left, top, right, bottom = result.box
    assert 720 < left < 740
    assert 1340 < top < 1360
    assert 1390 < bottom < 1410
    assert 915 < right < 935
    assert result.review_required
    assert result.label == "net_pay_dark_bar_candidate"


def test_missing_second_bar_never_infers_net_salary():
    with pytest.raises(AmountCellLocationError, match="two summary bars"):
        locate_dark_bar_net_pay_cell(sample_image(two_bars=False), (heading(),))


def test_missing_or_uncertain_earnings_anchor_blocks_fallback():
    with pytest.raises(AmountCellLocationError, match="anchor"):
        locate_dark_bar_net_pay_cell(sample_image(), ())
    with pytest.raises(AmountCellLocationError, match="anchor"):
        locate_dark_bar_net_pay_cell(sample_image(), (heading(confidence=15),))


def test_wrong_scale_fails_closed():
    image = Image.new("RGB", (450, 700), "white")
    with pytest.raises(AmountCellLocationError, match="too small"):
        locate_dark_bar_net_pay_cell(image, (heading(),))
