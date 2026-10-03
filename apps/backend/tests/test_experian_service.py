from __future__ import annotations

import base64
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from services import experian_service


def _row(configuration: dict | None = None):
    return SimpleNamespace(
        environment="uat",
        is_enabled=True,
        encrypted_credentials="encrypted",
        configuration=configuration or {
            "region": "lesotho",
            "product": "normal_search_v2",
            "origin": "LNHUB",
            "origin_version": "1.0",
            "dll_version": "1.0",
            "response_mapping": {},
        },
    )


def _context(**overrides):
    value = {
        "national_id": "7408285107080",
        "passport_number": None,
        "forename": "Just",
        "forename2": "",
        "forename3": "",
        "surname": "Goofy",
        "gender": "M",
        "date_of_birth": "1974-08-28",
        "address1": "Maseru Central",
        "address2": "Maseru",
        "address3": "",
        "address4": "",
        "postal_code": "100",
        "cell_tel_no": "59001394",
        "enquiry_purpose": 12,
        "result_type": "JSON",
        "cs_data": True,
        "cpa_plus_nlr_data": True,
        "deeds": False,
        "directors": False,
        "run_compuscore": True,
        "run_codix": False,
        "address_mandatory": True,
    }
    value.update(overrides)
    return value


def test_build_normal_search_payload_matches_lesotho_contract(monkeypatch):
    monkeypatch.setattr(experian_service, "_credentials", lambda row: {"username": "user", "password": "pass"})

    payload = experian_service.build_normal_search_payload(_row(), context=_context())

    assert payload["username"] == "user"
    assert payload["password"] == "pass"
    assert payload["myOrigin"] == "LNHUB"
    assert payload["dllVersion"] == "1.0"

    criteria = payload["searchCriteria"]
    assert criteria["csData"] == "Y"
    assert criteria["cpaPlusNLRData"] == "Y"
    assert criteria["deeds"] == "N"
    assert criteria["directors"] == "N"
    assert criteria["runCompuScore"] == "Y"
    assert criteria["runCodix"] == "N"
    assert criteria["passportFlag"] == "N"
    assert criteria["identity_number"] == "7408285107080"
    assert criteria["forename"] == "Just"
    assert criteria["surname"] == "Goofy"
    assert criteria["gender"] == "M"
    assert criteria["dateOfBirth"] == "19740828"
    assert criteria["postalCode"] == "100"
    assert criteria["clientConsent"] == "Y"
    assert criteria["adrs_Mandatory"] == "Y"
    assert criteria["resultType"] == "JSON"
    assert criteria["enqPurpose"] == 12


def test_build_normal_search_payload_uses_passport_flag(monkeypatch):
    monkeypatch.setattr(experian_service, "_credentials", lambda row: {"username": "user", "password": "pass"})

    payload = experian_service.build_normal_search_payload(
        _row(),
        context=_context(national_id=None, passport_number="P1234567"),
    )

    assert payload["searchCriteria"]["passportFlag"] == "Y"
    assert payload["searchCriteria"]["identity_number"] == "P1234567"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("gender", ""),
        ("date_of_birth", None),
        ("postal_code", ""),
        ("address1", ""),
        ("address2", ""),
    ],
)
def test_build_normal_search_payload_rejects_missing_required_fields(monkeypatch, key, value):
    monkeypatch.setattr(experian_service, "_credentials", lambda row: {"username": "user", "password": "pass"})

    with pytest.raises(experian_service.ExperianConfigurationError):
        experian_service.build_normal_search_payload(_row(), context=_context(**{key: value}))


def test_decode_ret_data_extracts_pk_zip_json():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps({"enquiryId": "123", "score": 640}))

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    decoded = experian_service._decode_ret_data(encoded)

    assert decoded["encoding"] == "base64"
    assert decoded["zip"] is True
    assert decoded["documents"][0]["name"] == "report.json"
    assert decoded["documents"][0]["json"]["enquiryId"] == "123"


def test_normalize_response_only_uses_explicit_mapping():
    payload = {"decoded": {"documents": [{"json": {"score": 640, "monthly": 1200}}]}}
    configuration = {
        "response_mapping": {
            "score": "decoded.documents.0.json.score",
            "monthly_commitments": "decoded.documents.0.json.monthly",
        }
    }

    normalized = experian_service.normalize_response(payload, configuration)

    assert normalized["score"] == 640
    assert normalized["monthly_commitments"] == 1200.0
    assert normalized["defaults_count"] == 0
