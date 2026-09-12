from pathlib import Path


def test_company_client_case_model_and_routes_are_present():
    backend = Path(__file__).parents[1]
    model = (backend / "database" / "models" / "company_client_case.py").read_text(encoding="utf-8")
    router = (backend / "routers" / "company_clients.py").read_text(encoding="utf-8")
    migration = (backend / "alembic" / "versions" / "x7k1m3n5p680_company_client_comments_and_legal_actions.py").read_text(encoding="utf-8")

    assert '__tablename__ = "company_client_case_entries"' in model
    assert '@router.get("/case-records"' in router
    assert '"/{account_id}/case-entries"' in router
    assert '"/{account_id}/case-entries/{entry_id}"' in router
    assert 'revision: str = "x7k1m3n5p680"' in migration
    assert '("w6h8j0k2m470", "f1a9c4e7b620")' in migration
