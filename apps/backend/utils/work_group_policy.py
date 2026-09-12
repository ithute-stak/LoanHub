from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkGroupPolicy:
    code: str
    name: str
    aliases: tuple[str, ...] = ()


WORK_GROUP_POLICY: tuple[WorkGroupPolicy, ...] = (
    WorkGroupPolicy(
        code="L/GOV",
        name="Lesotho Government",
        aliases=("LESOTHO GOVERNMENT",),
    ),
    WorkGroupPolicy(
        code="LMPS",
        name="Lesotho Mounted Police Service",
        aliases=("LESOTHO MOUNTED POLICE SERVICE",),
    ),
    WorkGroupPolicy(
        code="LCS",
        name="Lesotho Correctional Service",
        aliases=("LESOTHO CORRECTIONAL SERVICE",),
    ),
    WorkGroupPolicy(
        code="LDF",
        name="Lesotho Defence Force",
        aliases=("LESOTHO DEFENCE FORCE",),
    ),
    WorkGroupPolicy(
        code="NSS",
        name="National Security Service",
        aliases=("NATIONAL SECURITY SERVICE",),
    ),
    WorkGroupPolicy(code="NDSO", name="NDSO"),
    WorkGroupPolicy(
        code="PENSIONS",
        name="Pensions",
        aliases=("PENSION", "PENSIONERS"),
    ),
    WorkGroupPolicy(code="NGO", name="NGO"),
    WorkGroupPolicy(code="LEMS", name="LEMS"),
    WorkGroupPolicy(
        code="LE HAE",
        name="LE HAE",
        aliases=("LEHAE",),
    ),
)

WORK_GROUP_CODES: tuple[str, ...] = tuple(item.code for item in WORK_GROUP_POLICY)
WORK_GROUP_NAMES: dict[str, str] = {
    item.code: item.name for item in WORK_GROUP_POLICY
}


def normalize_work_group_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


_POLICY_LOOKUP: dict[str, WorkGroupPolicy] = {}
for _item in WORK_GROUP_POLICY:
    for _value in (_item.code, _item.name, *_item.aliases):
        _POLICY_LOOKUP[normalize_work_group_key(_value)] = _item


def work_group_policy_for(value: str | None) -> WorkGroupPolicy | None:
    return _POLICY_LOOKUP.get(normalize_work_group_key(value))


def is_supported_work_group(value: str | None) -> bool:
    return work_group_policy_for(value) is not None


def work_group_sort_key(value: str | None) -> int:
    policy = work_group_policy_for(value)
    if policy is None:
        return len(WORK_GROUP_POLICY)
    return WORK_GROUP_CODES.index(policy.code)
