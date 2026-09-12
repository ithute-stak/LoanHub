import pytest
from fastapi import HTTPException

from database.models.employer_group import EmployerGroup
from services.employer_group_service import (
    ensure_central_work_groups,
    normalize_employer_group_code,
)
from utils.work_group_policy import (
    WORK_GROUP_CODES,
    WORK_GROUP_NAMES,
    is_supported_work_group,
    work_group_policy_for,
)


EXPECTED_WORK_GROUPS = (
    "L/GOV",
    "LMPS",
    "LCS",
    "LDF",
    "NSS",
    "NDSO",
    "PENSIONS",
    "NGO",
    "LEMS",
    "LE HAE",
)


class _FakeQuery:
    def __init__(self, groups: list[EmployerGroup]):
        self.groups = groups

    def filter(self, *_args):
        return self

    def all(self) -> list[EmployerGroup]:
        return list(self.groups)


class _FakeSession:
    def __init__(self, groups: list[EmployerGroup] | None = None):
        self.groups = list(groups or [])
        self.commit_count = 0

    def query(self, _model):
        return _FakeQuery(self.groups)

    def add(self, group: EmployerGroup) -> None:
        self.groups.append(group)

    def commit(self) -> None:
        self.commit_count += 1


def test_central_work_group_policy_contains_exact_supported_catalogue():
    assert WORK_GROUP_CODES == EXPECTED_WORK_GROUPS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("L/Gov", "L/GOV"),
        (" l/gov ", "L/GOV"),
        ("LMPs", "LMPS"),
        ("NSs", "NSS"),
        ("le   hae", "LE HAE"),
        ("Lesotho Government", "L/GOV"),
        ("Lesotho Mounted Police Service", "LMPS"),
    ],
)
def test_work_group_aliases_are_canonicalized(raw: str, expected: str):
    policy = work_group_policy_for(raw)
    assert policy is not None
    assert policy.code == expected
    assert is_supported_work_group(raw)


@pytest.mark.parametrize("code", EXPECTED_WORK_GROUPS)
def test_employer_group_code_normalizer_accepts_only_central_codes(code: str):
    assert normalize_employer_group_code(code) == code


def test_arbitrary_employer_group_code_is_rejected():
    with pytest.raises(HTTPException) as exc:
        normalize_employer_group_code("ACME LTD")

    assert exc.value.status_code == 422
    assert "central work groups" in str(exc.value.detail)


def test_central_work_groups_are_seeded_exactly_once():
    db = _FakeSession()

    created, updated = ensure_central_work_groups(db)

    assert created == len(EXPECTED_WORK_GROUPS)
    assert updated == 0
    assert db.commit_count == 1
    assert tuple(group.code for group in db.groups) == EXPECTED_WORK_GROUPS
    assert {
        group.code: group.name for group in db.groups
    } == WORK_GROUP_NAMES
    assert all(group.is_active for group in db.groups)

    created_again, updated_again = ensure_central_work_groups(db)

    assert (created_again, updated_again) == (0, 0)
    assert db.commit_count == 1
    assert len(db.groups) == len(EXPECTED_WORK_GROUPS)


def test_central_work_group_seed_repairs_name_and_active_state():
    existing = EmployerGroup(
        code="LMPS",
        name="Old Police Group Name",
        is_active=False,
    )
    db = _FakeSession([existing])

    created, updated = ensure_central_work_groups(db)

    assert created == len(EXPECTED_WORK_GROUPS) - 1
    assert updated == 1
    assert db.commit_count == 1
    assert existing.name == WORK_GROUP_NAMES["LMPS"]
    assert existing.is_active is True
