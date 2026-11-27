"""Regression tests for the independent ledger reviewer eligibility gate."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import CompanyStatus, UserRole
from services.principal_x_reviewer_authorization import require_independent_ledger_reviewers


@pytest.fixture
def scenario():
    company, maker, checker = uuid4(), uuid4(), uuid4()
    organization = SimpleNamespace(is_active=True, status=CompanyStatus.APPROVED)
    actors = [SimpleNamespace(id=maker, is_active=True),
              SimpleNamespace(id=checker, is_active=True)]
    memberships = [
        SimpleNamespace(user_id=maker, role=UserRole.FINANCE_OFFICER,
                        is_active=True, branch_id=None),
        SimpleNamespace(user_id=checker, role=UserRole.AUDITOR,
                        is_active=True, branch_id=None),
    ]
    calls = []

    def execute(statement):
        calls.append(statement)
        if len(calls) == 1:
            return SimpleNamespace(scalar_one_or_none=lambda: organization)
        rows = actors if len(calls) == 2 else memberships
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))

    db = SimpleNamespace(
        no_autoflush=nullcontext(), execute=execute,
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
    )
    return SimpleNamespace(db=db, company=company, maker=maker, checker=checker,
                           organization=organization, actors=actors,
                           memberships=memberships, calls=calls)


def run(scenario, **overrides):
    scope = dict(company_id=scenario.company, maker_user_id=scenario.maker,
                 checker_user_id=scenario.checker)
    scope.update(overrides)
    return require_independent_ledger_reviewers(scenario.db, **scope)


def test_independent_finance_and_audit_reviewers(scenario):
    assert run(scenario) is None
    assert len(scenario.calls) == 3
    from sqlalchemy.dialects import postgresql
    for statement in scenario.calls:
        assert "FOR SHARE" in str(statement.compile(dialect=postgresql.dialect()))
    membership_query = scenario.calls[-1].compile(dialect=postgresql.dialect())
    assert "company_staff.company_id =" in str(membership_query)
    assert scenario.company in membership_query.params.values()


def test_self_approval_rejected_before_database_access(scenario):
    with pytest.raises(ValueError, match="Independent maker"):
        run(scenario, checker_user_id=scenario.maker)
    assert not scenario.calls


@pytest.mark.parametrize("field", ["company_id", "maker_user_id", "checker_user_id"])
def test_unverified_scope_rejected(scenario, field):
    with pytest.raises(ValueError, match="Verified reviewer scope"):
        run(scenario, **{field: "unverified"})
    assert not scenario.calls


def test_non_postgresql_rejected(scenario):
    scenario.db.get_bind = lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        run(scenario)


@pytest.mark.parametrize("inactive", [True, False])
def test_unapproved_or_inactive_company_rejected(scenario, inactive):
    if inactive:
        scenario.organization.is_active = False
    else:
        scenario.organization.status = CompanyStatus.SUSPENDED
    with pytest.raises(ValueError, match="Active approved company"):
        run(scenario)


@pytest.mark.parametrize("actor", [0, 1])
def test_inactive_account_rejected(scenario, actor):
    scenario.actors[actor].is_active = False
    with pytest.raises(ValueError, match="Active independent reviewers"):
        run(scenario)


@pytest.mark.parametrize("actor", [0, 1])
@pytest.mark.parametrize("defect", ["inactive", "branch", "missing", "role"])
def test_ineligible_membership_rejected(scenario, actor, defect):
    if defect == "inactive":
        scenario.memberships[actor].is_active = False
    elif defect == "branch":
        scenario.memberships[actor].branch_id = uuid4()
    elif defect == "missing":
        scenario.memberships.pop(actor)
    else:
        scenario.memberships[actor].role = UserRole.PLATFORM_ADMIN
    with pytest.raises(ValueError, match="authority"):
        run(scenario)


def test_two_distinct_company_owners_eligible(scenario):
    for membership in scenario.memberships:
        membership.role = UserRole.COMPANY_OWNER
    assert run(scenario) is None
