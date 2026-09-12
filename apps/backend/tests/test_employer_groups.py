import pytest
from fastapi import HTTPException

from services.employer_group_service import normalize_employer_group_code, normalize_employer_group_name


def test_employer_group_code_is_normalized_for_search_and_storage():
    assert normalize_employer_group_code(" l/gov ") == "L/GOV"
    assert normalize_employer_group_code("lMps") == "LMPS"
    assert normalize_employer_group_code("le   hae") == "LE HAE"


def test_employer_group_code_rejects_unsupported_characters():
    with pytest.raises(HTTPException):
        normalize_employer_group_code("LCS#")


def test_employer_group_name_collapses_whitespace():
    assert normalize_employer_group_name("  Lesotho   Government ") == "Lesotho Government"
