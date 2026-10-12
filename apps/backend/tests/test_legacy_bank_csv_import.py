"""Legacy import should preserve leading zeroes and refuse invalid rows."""
import pytest
from services.legacy_bank_import import parse_legacy_csv


GROUPS = {"force": "group-a", "civil": "group-b", "s/e": "group-c"}


def test_header_rows_and_leading_zeroes_are_preserved():
    data = ("Work group,Client name,Account number,Branch code,Amount\n"
            "Force,Thato,00123456789,010,125.50\n"
            "Civil,Mpho,9012345678,000123,250.00\n").encode()
    records, issues = parse_legacy_csv(data, known_groups=GROUPS)
    assert issues == []
    assert len(records) == 2
    assert records[0]["account"] == "00123456789"
    assert records[0]["branch"] == "000010"
    assert str(records[0]["amount"]) == "125.50"
    assert records[1]["group_id"] == "group-b"


def test_invalid_amount_account_and_unknown_group_report_row_numbers():
    data = ("Force,Alice,1234567890,123,NaN\n"
            "S/E,Bob,00001111,123,80.00\n"
            "Unknown,Charlie,1234567,123,100\n"
            "Civil,David,=SUM(1),123,100\n").encode()
    records, issues = parse_legacy_csv(data, known_groups=GROUPS)
    assert len(records) == 1
    assert records[0]["name"] == "Bob"
    assert [(row["row"], row["reason"]) for row in issues] == [
        (1, "Invalid deduction amount"),
        (3, "Unknown work group"),
        (4, "Account must contain 6-20 digits"),
    ]


def test_limit_and_invalid_encoding_fail_closed():
    with pytest.raises(ValueError, match="UTF-8"):
        parse_legacy_csv(b"\xff\xfe", known_groups=GROUPS)
    with pytest.raises(ValueError, match="2 MB"):
        parse_legacy_csv(b"a" * 2_000_001, known_groups=GROUPS)
    with pytest.raises(ValueError, match="5000 rows"):
        parse_legacy_csv(("Force,A,123456,123,1\n" * 5001).encode(), known_groups=GROUPS)
