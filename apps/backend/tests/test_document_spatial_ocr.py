"""Spatial OCR regression tests with synthetic positions and identifiers."""
import pytest

from services.document_intelligence_reader import DocumentReadError
from services.document_spatial_ocr import (
    date_strings_in_stamp_crop,
    group_lines,
    parse_tesseract_tsv,
    propose_stamp_regions,
)

TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)


def _record(text, left, top, block, line=1, confidence=92):
    return (
        f"5\t1\t{block}\t1\t{line}\t1\t"
        f"{left}\t{top}\t60\t20\t{confidence}\t{text}"
    )


def test_columns_at_same_height_are_not_merged():
    tsv = "\n".join([
        TSV_HEADER,
        _record("Earnings", 20, 100, 1),
        _record("Deductions", 350, 100, 2),
    ])
    words = parse_tesseract_tsv(tsv, width=800, height=900)
    lines = group_lines(words)
    assert len(lines) == 2
    assert lines[0].text == "Earnings"
    assert lines[1].text == "Deductions"
    assert lines[1].left == 350


def test_stamp_candidates_anywhere_on_page():
    tsv = "\n".join([
        TSV_HEADER,
        _record("STAMP", 700, 700, 1),
        _record("STAFF", 20, 20, 2),
        _record("OFFICIAL", 400, 250, 3),
    ])
    lines = group_lines(parse_tesseract_tsv(tsv, width=900, height=900))
    regions = propose_stamp_regions(lines, width=900, height=900, padding_px=80)
    assert len(regions) == 2
    assert regions[0].top == 170
    assert regions[1].right == 840
    assert all(region.requires_review for region in regions)


def test_crop_date_candidate_is_not_assumed_to_be_verified():
    tsv = "\n".join([
        TSV_HEADER,
        _record("23-Nov-2026", 100, 100, 1),
        _record("Date", 100, 130, 2),
    ])
    lines = group_lines(parse_tesseract_tsv(tsv, width=900, height=900))
    assert date_strings_in_stamp_crop(lines) == ("23-Nov-2026",)


def test_invalid_tsv_bounds_rejected():
    with pytest.raises(DocumentReadError, match="outside image"):
        parse_tesseract_tsv(
            "\n".join([TSV_HEADER, _record("STAMP", 900, 100, 1)]),
            width=900,
            height=900,
        )


def test_negative_confidence_metadata_is_not_a_word():
    tsv = "\n".join([TSV_HEADER, _record("", 0, 0, 1, confidence=-1)])
    assert parse_tesseract_tsv(tsv, width=900, height=900) == ()


def test_no_stamp_anchor_yields_no_candidate():
    words = parse_tesseract_tsv(
        "\n".join([TSV_HEADER, _record("NetPay", 40, 40, 1)]),
        width=900, height=900
    )
    assert propose_stamp_regions(group_lines(words), width=900, height=900) == ()
