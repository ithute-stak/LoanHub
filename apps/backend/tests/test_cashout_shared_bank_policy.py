"""Legacy Cashout and Legacy CSV must share the exact same bank policy."""
import pytest

from services.legacy_bank_routing import BANK_RULES, resolve_legacy_bank
from utils.banking import BANKING_POLICY, standard_bank_fields, validate_account_number_for_bank


@pytest.mark.parametrize("bank,branch,prefixes", BANK_RULES)
def test_cashout_rules_derive_from_legacy_csv(bank, branch, prefixes):
    assert BANKING_POLICY[bank]["code"] == branch
    assert BANKING_POLICY[bank]["prefixes"] == prefixes
    assert standard_bank_fields(bank) == (bank, "Maseru Central", branch)
    for prefix in prefixes:
        account = prefix + "123456789"
        assert resolve_legacy_bank(account) == (bank, branch)
        assert validate_account_number_for_bank(bank, account) == account


def test_cashout_rejects_mismatched_bank_account_prefix():
    with pytest.raises(ValueError, match="belongs to FNB"):
        validate_account_number_for_bank("STD", "6123456789")


def test_unknown_prefix_is_not_guessed():
    assert resolve_legacy_bank("99123456789") is None
    with pytest.raises(ValueError):
        validate_account_number_for_bank("PB", "99123456789")
