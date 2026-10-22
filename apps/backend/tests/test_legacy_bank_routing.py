from services.legacy_bank_routing import resolve_legacy_bank
from services.bank_submission_export import build_bank_submission_zip
from io import BytesIO
from zipfile import ZipFile


def test_configured_bank_prefix_rules():
    assert resolve_legacy_bank("63057452012") == ("FNB", "280061")
    assert resolve_legacy_bank("9080004214532") == ("STD", "060667")
    assert resolve_legacy_bank("10000012345") == ("PB", "500100")
    assert resolve_legacy_bank("11000012345") == ("NB", "390161")
    assert resolve_legacy_bank("12000012345") == ("NB", "390161")
    assert resolve_legacy_bank("99900012345") == ("NB", "390161")
    assert resolve_legacy_bank("23000012345") == ("NB", "390161")
    assert resolve_legacy_bank("9990001234567") is None


def test_legacy_zip_accepts_configured_branch_without_guessing():
    bank, branch = resolve_legacy_bank("9080004214532")
    payload, summary = build_bank_submission_zip([
        {"name": "Mamothusi Mohapi", "bank": bank, "account": "9080004214532",
         "branch": branch, "group": "CIVIL", "installment": "2500", "balance": "2500"}
    ], lender_name="Batlokoa Financial Services")
    assert summary["rows"] == 1
    assert not summary["excluded"]
    with ZipFile(BytesIO(payload)) as archive:
        assert archive.namelist() == ["STD-civil.csv"]
        assert b"060667" in archive.read("STD-civil.csv")
