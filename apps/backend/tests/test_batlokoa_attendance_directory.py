"""Security regressions for the disabled-by-default attendance service."""
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Response

from routers.batlokoa_attendance_directory import authorize_directory, employees
from database.models.enums import UserRole


@pytest.fixture
def config(monkeypatch):
    company = uuid4()
    token = "synthetic-test-only-" + "x" * 40
    monkeypatch.setenv("BATLOKOA_ATTENDANCE_DIRECTORY_ENABLED", "true")
    monkeypatch.setenv("BATLOKOA_ATTENDANCE_DIRECTORY_TOKEN", token)
    monkeypatch.setenv("BATLOKOA_ATTENDANCE_DIRECTORY_COMPANY_ID", str(company))
    return company, "Bearer " + token


def test_disabled(monkeypatch, config):
    monkeypatch.setenv("BATLOKOA_ATTENDANCE_DIRECTORY_ENABLED", "false")
    with pytest.raises(HTTPException) as exc:
        authorize_directory(*config)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("header", [None, "Bearer wrong", "Bearer é"])
def test_bad_credentials(config, header):
    with pytest.raises(HTTPException) as exc:
        authorize_directory(config[0], header)
    assert exc.value.status_code == 401


def test_wrong_company(config):
    with pytest.raises(HTTPException) as exc:
        authorize_directory(uuid4(), config[1])
    assert exc.value.status_code == 403


def test_directory_filters_ineligible_memberships(config):
    company, header = config
    eligible, inactive, ambiguous, disabled, secondary = [uuid4() for _ in range(5)]
    db = MagicMock()
    company_query, staff_query = MagicMock(), MagicMock()
    db.query.side_effect = [company_query, staff_query]
    company_query.filter.return_value.first.return_value = (company,)
    staff_query.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (eligible, UserRole.LOAN_OFFICER, True, True, True),
        (inactive, UserRole.LOAN_OFFICER, False, True, True),
        (ambiguous, UserRole.LOAN_OFFICER, True, True, True),
        (ambiguous, UserRole.BRANCH_MANAGER, True, True, True),
        (disabled, UserRole.LOAN_OFFICER, True, True, False),
        (secondary, UserRole.LOAN_OFFICER, True, False, True),
    ]
    response = Response()
    result = employees(response, company, limit=100, authorization=header, db=db)
    assert result["complete"] is True
    assert len(result["employees"]) == 1
    assert result["employees"][0]["employee_id"] == str(eligible)
    assert response.headers["Cache-Control"] == "no-store"


def test_unauthorized_never_queries_database(config):
    db = MagicMock()
    with pytest.raises(HTTPException):
        employees(Response(), config[0], limit=100, authorization=None, db=db)
    db.query.assert_not_called()
