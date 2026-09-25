from pathlib import Path


def test_backend_exposes_docker_readiness_endpoint():
    source = Path("main.py").read_text(encoding="utf-8")
    assert '@app.get("/health/ready"' in source
    assert 'db.execute(text("SELECT 1"))' in source
