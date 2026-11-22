"""Stamp candidate binding detects changing visual company branding inputs."""
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.document_studio_letter_branding_evidence import capture_letter_branding_evidence


def fixture():
    tenant = uuid4()
    document = SimpleNamespace(company_id=tenant)
    company = SimpleNamespace(
        id=tenant, name="Batlokoa Example Tenant", registration_number="REG",
        license_number="LIC", phone="+266 50000000", email="finance@example.test",
        address="Maseru", website=None, district=None,
    )
    return document, company


def capture(document, company, left=b"loanhub-logo", right=b"company-logo"):
    return capture_letter_branding_evidence(
        document=document, company=company,
        left_logo=left, right_logo=right,
    )


def test_same_exact_branding_bytes_produce_matching_evidence():
    document, company = fixture()
    assert capture(document, company) == capture(document, company)


@pytest.mark.parametrize("field,value", [
    ("name", "Changed legal company name"), ("registration_number", "OTHER"),
    ("phone", "+266 00000000"), ("email", "different@example.test"),
    ("website", "example.com"), ("address", "Another address"),
])
def test_company_identity_changes_invalidate_branding_digest(field, value):
    document, company = fixture()
    original = capture(document, company)
    setattr(company, field, value)
    assert original.combined_sha256 != capture(document, company).combined_sha256


@pytest.mark.parametrize("left,right", [
    (b"loanhub-logo-new", b"company-logo"),
    (b"loanhub-logo", b"company-logo-new"),
    (None, b"company-logo"),
    (b"loanhub-logo", None),
])
def test_logo_bytes_or_visibility_change_invalidate_branding_digest(left, right):
    document, company = fixture()
    original = capture(document, company)
    assert original.combined_sha256 != capture(document, company, left, right).combined_sha256


def test_cross_tenant_branding_rejected():
    document, company = fixture()
    company.id = uuid4()
    with pytest.raises(PermissionError, match="another tenant"):
        capture(document, company)


@pytest.mark.parametrize("logo", ["untrusted", b"", object()])
def test_invalid_branding_payload_rejected(logo):
    document, company = fixture()
    with pytest.raises(PermissionError, match="Invalid resolved"):
        capture(document, company, right=logo)
