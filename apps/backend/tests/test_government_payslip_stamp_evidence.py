"""Test stamp candidates without any real employee/payslip data."""
from datetime import date

from services.document_intelligence_foundation import StampStatus
from services.document_spatial_ocr import OCRLine, OCRWord, StampRegion
from services.government_payslip_stamp_evidence import assess_spatial_stamp


def line(text, left, top, confidence=95):
    word = OCRWord(text, confidence, left, top, 160, 20, 1, 1, 1)
    return OCRLine(text, (word,), left, top, left + 160, top + 20)


def test_recent_stamp_anywhere_on_page_is_date_valid_but_not_authenticity_verified():
    lines = [
        line("01 Jan 1990", 100, 100),  # Example date of birth outside stamp
        line("23 Nov 2026", 700, 800),
    ]
    box = StampRegion(650, 740, 950, 920, ("stamp",))
    result = assess_spatial_stamp(lines, [box], assessed_at=date(2026, 11, 24))
    assert result.assessment.status == StampStatus.VALID_DATE
    assert result.candidate_dates == (date(2026, 11, 23),)
    assert result.requires_manual_review
    assert "stamp_authenticity_unverified" in result.review_reasons


def test_no_stamp_region_does_not_infer_from_other_document_dates():
    result = assess_spatial_stamp(
        [line("23 Nov 2026", 100, 100)], [],
        assessed_at=date(2026, 11, 24),
    )
    assert result.assessment.status == StampStatus.MISSING
    assert "stamp_region_not_detected" in result.review_reasons


def test_numeric_date_remains_ambiguous():
    result = assess_spatial_stamp(
        [line("03/04/2026", 700, 800)],
        [StampRegion(600, 700, 950, 900, ("official",))],
        assessed_at=date(2026, 11, 24),
    )
    assert result.assessment.status == StampStatus.MISSING
    assert result.unreadable_dates == ("03/04/2026",)
    assert "stamp_date_format_ambiguous" in result.review_reasons


def test_expired_and_future_stamp_dates_are_flagged():
    box = StampRegion(600, 700, 950, 900, ("stamp",))
    expired = assess_spatial_stamp([line("23 Aug 2026", 700, 800)], [box], assessed_at=date(2026, 11, 24))
    future = assess_spatial_stamp([line("25 Nov 2026", 700, 800)], [box], assessed_at=date(2026, 11, 24))
    assert expired.assessment.status == StampStatus.EXPIRED
    assert future.assessment.status == StampStatus.FUTURE_DATE


def test_conflicting_stamp_dates_are_not_accepted():
    box = StampRegion(500, 600, 1000, 1000, ("stamp",))
    result = assess_spatial_stamp(
        [line("23 Sep 2026", 600, 700), line("24 Oct 2026", 600, 800)],
        [box], assessed_at=date(2026, 11, 24),
    )
    assert result.assessment.status == StampStatus.AMBIGUOUS


def test_low_confidence_date_requires_review():
    box = StampRegion(600, 700, 950, 900, ("stamp",))
    result = assess_spatial_stamp([line("23 Nov 2026", 700, 800, 35)], [box], assessed_at=date(2026, 11, 24))
    assert "stamp_date_low_confidence" in result.review_reasons
