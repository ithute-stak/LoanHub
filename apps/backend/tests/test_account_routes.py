from main import app


def test_authenticated_account_routes_are_registered():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/auth/account": {"get"},
        "/api/v1/auth/account/contact": {"patch"},
        "/api/v1/auth/account/profile": {"put"},
        "/api/v1/auth/account/password": {"post"},
        "/api/v1/auth/account/sessions": {"get"},
        "/api/v1/auth/account/sessions/revoke-others": {"post"},
        "/api/v1/auth/account/sessions/revoke-all": {"post"},
        "/api/v1/auth/account/activity": {"get"},
    }

    for path, methods in expected.items():
        assert path in paths
        assert methods.issubset(paths[path])
