"""Connection-test errors must not disclose provider responses or credentials."""
import pytest

from integrations.cdas import CdasError
from routers.platform_cdas import _connection_test_error_detail


@pytest.mark.parametrize("status,expected", [
    (401, "authentication"),
    (403, "authentication"),
    (429, "allowance"),
    (408, "timed out"),
    (504, "timed out"),
    (503, "unavailable"),
    (502, "failed"),
])
def test_connection_error_detail_is_safe_and_actionable(status, expected):
    secret = "SECRET_PROVIDER_RESPONSE_123"
    message = _connection_test_error_detail(CdasError(status, secret))
    assert expected in message.lower()
    assert secret not in message


def test_connection_error_never_echoes_provider_details():
    secret = "password=DO_NOT_LOG"
    error = CdasError(502, "upstream refused", {"Authorization": secret})
    assert secret not in _connection_test_error_detail(error)
    assert "upstream refused" not in _connection_test_error_detail(error)
