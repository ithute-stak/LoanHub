from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECURITY = ROOT / "apps" / "backend" / "core" / "security_middleware.py"
CONFIG = ROOT / "apps" / "backend" / "database" / "config" / "config.py"


def test_authenticated_api_has_separate_rate_limit_tier() -> None:
    source = SECURITY.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

    assert "AUTHENTICATED_RATE_LIMIT" in config
    assert "current_user_id.get()" in source
    assert 'scope = "user"' in source
    assert 'scope = "auth"' in source
    assert 'scope = "api"' in source
    assert "settings.AUTHENTICATED_RATE_LIMIT" in source
    assert "settings.AUTH_RATE_LIMIT" in source
    assert "settings.RATE_LIMIT" in source


def test_authenticated_identity_is_not_shared_ip_only() -> None:
    source = SECURITY.read_text(encoding="utf-8")

    assert 'identity = hashlib.sha256(str(authenticated_user_id).encode("utf-8")).hexdigest()[:24]' in source
    assert "X-RateLimit-Scope" in source
    assert "request.method.upper() == 'OPTIONS'" in source
