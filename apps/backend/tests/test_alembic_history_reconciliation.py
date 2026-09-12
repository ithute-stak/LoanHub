from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"


def _read(name: str) -> str:
    return (VERSIONS / name).read_text(encoding="utf-8")


def test_legacy_and_experian_migration_histories_converge() -> None:
    paybridge = _read("j0z4b6c8e910_lelefapaygate_database_configuration.py")
    settlement = _read("k1a5c7d9e011_add_company_settlement_destination.py")
    contract = _read("k1a5c7d9f011_company_default_loan_contract.py")
    installment = _read("l2b6d8e0f012_installment_due_date_requests.py")
    legacy = _read("m3c7e9f1a013_legacy_cashbook_capture.py")
    experian = _read("n4d8f0a2b014_experian_credit_bureau_enquiries.py")
    platform = _read("p0a1b2c3d015_platform_experian_owner_control.py")
    merge = _read("q1c4e7g0h016_merge_legacy_and_experian_heads.py")

    assert 'revision = "j0z4b6c8e910"' in paybridge

    assert 'revision = "k1a5c7d9e011"' in settlement
    assert 'down_revision = "j0z4b6c8e910"' in settlement
    assert 'revision = "l2b6d8e0f012"' in installment
    assert 'down_revision = "k1a5c7d9e011"' in installment
    assert 'revision = "m3c7e9f1a013"' in legacy
    assert 'down_revision = "l2b6d8e0f012"' in legacy

    assert 'revision = "k1a5c7d9f011"' in contract
    assert 'down_revision = "j0z4b6c8e910"' in contract
    assert 'revision = "n4d8f0a2b014"' in experian
    assert 'down_revision = "k1a5c7d9f011"' in experian
    assert 'revision = "p0a1b2c3d015"' in platform
    assert 'down_revision = "n4d8f0a2b014"' in platform

    assert 'revision = "q1c4e7g0h016"' in merge
    assert 'down_revision = ("p0a1b2c3d015", "m3c7e9f1a013")' in merge
