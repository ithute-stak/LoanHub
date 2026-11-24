from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.company_stamp_configuration import stamp_from_company


def test_stamp_resolves_approved_company_fields_without_hardcoding_tenant():
    tenant_id = uuid4()
    company = SimpleNamespace(
        id=tenant_id, name="Example Loans (Pty) Ltd",
        address="Maseru, Lesotho", phone="+266 50000000",
        email="company@example.test", registration_number="REG-001",
        license_number="LIC-001",
    )
    stamp = stamp_from_company(company, authenticated_tenant_id=tenant_id)
    assert stamp.tenant_id == tenant_id
    assert stamp.legal_name == "Example Loans (Pty) Ltd"
    assert stamp.registration_number == "REG-001"
    assert stamp.license_number == "LIC-001"


def test_cross_tenant_configuration_rejected():
    company = SimpleNamespace(id=uuid4(), name="Wrong tenant")
    with pytest.raises(PermissionError):
        stamp_from_company(company, authenticated_tenant_id=uuid4())


def test_incomplete_company_contact_details_rejected():
    tenant_id = uuid4()
    company = SimpleNamespace(id=tenant_id, name="Company", address="",
                              phone="", email="")
    with pytest.raises(ValueError):
        stamp_from_company(company, authenticated_tenant_id=tenant_id)
