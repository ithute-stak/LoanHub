"""Spatial financial table separation uses synthetic, non-identifying OCR words."""
import pytest

from services.document_spatial_ocr import OCRWord
from services.government_payslip_spatial_layout import (
    AmbiguousPayslipLayout,
    separate_financial_columns,
)


def word(text, x, y, block, conf=96.0, width=80):
    return OCRWord(text, conf, x, y, width, 20, block, 1, 1)


def valid_words():
    return [
        word("Earnings", 80, 100, 1),
        word("Deductions", 550, 100, 2, width=120),
        word("Salary", 80, 160, 3),
        word("8826.00", 250, 160, 4),
        word("PAYE", 550, 160, 5),
        word("847.41", 710, 160, 6),
    ]


def test_separates_aligned_columns():
    result = separate_financial_columns(valid_words(), page_width=900)
    assert result.divider_x == 395
    assert [x.text for x in result.earnings] == ["Salary", "8826.00"]
    assert [x.text for x in result.deductions] == ["PAYE", "847.41"]
    assert not result.review_reasons


def test_rejects_word_crossing_column_boundary():
    words = valid_words() + [word("CORRUPT", 370, 180, 7, width=70)]
    with pytest.raises(AmbiguousPayslipLayout, match="crosses"):
        separate_financial_columns(words, page_width=900)


def test_low_confidence_is_flagged_not_silently_accepted():
    words = valid_words()
    words[-1] = word("847.41", 710, 160, 6, conf=31)
    result = separate_financial_columns(words, page_width=900)
    assert result.review_reasons == ("low_confidence_financial_word",)


def test_missing_or_duplicate_headings_rejected():
    with pytest.raises(AmbiguousPayslipLayout, match="missing or duplicate"):
        separate_financial_columns(valid_words()[1:], page_width=900)
    with pytest.raises(AmbiguousPayslipLayout, match="missing or duplicate"):
        separate_financial_columns(valid_words() + [word("Deductions", 600, 100, 8)], page_width=900)


def test_misaligned_headings_rejected():
    words = valid_words()
    words[1] = word("Deductions", 550, 250, 2, width=120)
    with pytest.raises(AmbiguousPayslipLayout, match="same row"):
        separate_financial_columns(words, page_width=900)


def test_overlapping_headings_rejected():
    words = valid_words()
    words[1] = word("Deductions", 200, 100, 2, width=120)
    with pytest.raises(AmbiguousPayslipLayout):
        separate_financial_columns(words, page_width=900)
