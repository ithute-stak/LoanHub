from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import UserRole
from routers import audit as audit_router


class FakeQuery:
    def options(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return 0

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


class FakeSession:
    def query(self, *args, **kwargs):
        return FakeQuery()


def test_audit_uses_selected_active_role(monkeypatch):
    company_id = uuid4()
    captured = {}

    def fake_resolve(db, current_user, x_company_id, x_active_role):
        captured["company_id"] = x_company_id
        captured["active_role"] = x_active_role
        return SimpleNamespace(
            role=UserRole.COMPANY_OWNER,
            company_id=company_id,
            branch_id=None,
        )

    monkeypatch.setattr(audit_router, "resolve_tenant_context", fake_resolve)

    response = audit_router.list_audit_events(
        page=1,
        page_size=30,
        action=None,
        entity_type=None,
        search=None,
        x_company_id=str(company_id),
        x_active_role=UserRole.COMPANY_OWNER.value,
        db=FakeSession(),
        current_user=SimpleNamespace(role=UserRole.COMPANY_OWNER),
    )

    assert captured == {
        "company_id": str(company_id),
        "active_role": UserRole.COMPANY_OWNER.value,
    }
    assert response.total == 0
    assert response.items == []
