"""Synthetic test geometry, no customer payroll information."""
import pytest

from services.document_spatial_ocr import OCRWord
from services.government_payslip_amount_locator import (
    AmountCellLocationError,
    locate_net_pay_cell,
)


def word(text, x, y, *, conf=95, w=40):
    return OCRWord(text, conf, x, y, w, 20, 1, 1, 1)


def test_locates_amount_only_to_right_of_net_pay_label():
    parts = [word("NET", 100, 200), word("PAY", 148, 200), word("2,651.29", 250, 200, w=110)]
    result = locate_net_pay_cell(parts, width=900, height=1000)
    assert result.box[0] > 188
    assert result.box[1] < 200 < result.box[3]
    assert result.review_required


def test_duplicate_net_pay_labels_are_not_accepted():
    parts = [word("NET", 100, 200), word("PAY", 148, 200),
             word("NET", 100, 500), word("PAY", 148, 500)]
    with pytest.raises(AmountCellLocationError, match="ambiguous"):
        locate_net_pay_cell(parts, width=900, height=1000)


def test_low_confidence_label_is_not_used():
    parts = [word("NET", 100, 200, conf=30), word("PAY", 148, 200)]
    with pytest.raises(AmountCellLocationError, match="missing"):
        locate_net_pay_cell(parts, width=900, height=1000)


def test_unrelated_words_in_cell_block_the_crop():
    parts = [word("NET", 100, 200), word("PAY", 148, 200),
             word("Existing", 250, 200, w=100)]
    with pytest.raises(AmountCellLocationError, match="non-monetary"):
        locate_net_pay_cell(parts, width=900, height=1000)


def test_vertical_or_rotated_label_is_not_inferred():
    parts = [word("NET", 100, 200), word("PAY", 150, 320)]
    with pytest.raises(AmountCellLocationError, match="missing"):
        locate_net_pay_cell(parts, width=900, height=1000)


def test_cell_outside_page_is_rejected():
    parts = [word("NET", 790, 200), word("PAY", 833, 200, w=40)]
    with pytest.raises(AmountCellLocationError, match="cannot be safely"):
        locate_net_pay_cell(parts, width=900, height=1000)
