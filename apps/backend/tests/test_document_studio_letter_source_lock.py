"""Non-routed letter locking checks live persisted data before stamp approval."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.document_studio_letter_source_lock import lock_current_letter_source


def case():
    tenant, document_id = uuid4(), uuid4()
    attrs = dict(
        id=document_id, company_id=tenant, template_key="formal_letter",
        version=2, content_html="<p>Approved letter source</p>",
        status="draft", finalized_at=None, is_deleted=False,
    )
    candidate, persisted = SimpleNamespace(**attrs), SimpleNamespace(**attrs)
    db = Mock()
    db.query.side_effect = [
        Mock(filter=lambda *args: Mock(
            populate_existing=lambda: Mock(
                with_for_update=lambda **kwargs: Mock(
                    one_or_none=lambda: persisted,
                )
            )
        )),
        Mock(filter=lambda *args: Mock(first=lambda: None)),
    ]
    return db, candidate, persisted, tenant


def test_persisted_source_lock_and_unsigned_letter_attestation():
    db, candidate, persisted, tenant = case()
    result = lock_current_letter_source(
        db=db, document=candidate, authenticated_tenant_id=tenant,
    )
    assert result.tenant_id == tenant
    assert result.document_id == candidate.id
    assert result.version == 2
    assert len(result.content_sha256) == 64
    assert len(result.render_snapshot_sha256) == 64
    db.commit.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("company_id", uuid4()), ("version", 3),
    ("content_html", "<p>Changed letter</p>"), ("template_key", "contract"),
    ("status", "published"), ("finalized_at", "date"),
])
def test_stale_candidate_denied(field, value):
    db, candidate, persisted, tenant = case()
    setattr(candidate, field, value)
    with pytest.raises(PermissionError, match="Letter rendering inputs changed"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )


@pytest.mark.parametrize("field,value", [
    ("is_deleted", True), ("status", "published"),
    ("version", 0), ("finalized_at", "date"), ("content_html", None),
])
def test_invalid_persisted_document_denied(field, value):
    db, candidate, persisted, tenant = case()
    setattr(persisted, field, value)
    with pytest.raises(PermissionError, match="deleted, finalized or invalid"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )


def test_existing_persisted_signature_denied():
    db, candidate, persisted, tenant = case()
    queries = iter(db.query.side_effect)
    db.query.side_effect = [
        next(queries),
        Mock(filter=lambda *args: Mock(first=lambda: (uuid4(),))),
    ]
    with pytest.raises(PermissionError, match="Stored letter signatures"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )


def test_missing_or_cross_tenant_persisted_row_denied():
    db, candidate, persisted, tenant = case()
    persisted.company_id = uuid4()
    with pytest.raises(PermissionError, match="Authoritative tenant letter"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )


@pytest.mark.parametrize("id_value", [None, "not-a-uuid"])
def test_unpersisted_document_denied_without_sql(id_value):
    db, candidate, persisted, tenant = case()
    candidate.id = id_value
    with pytest.raises(PermissionError, match="Persisted letter identity"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )
    db.query.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("page_size", "LETTER"), ("orientation", "landscape"),
    ("margin_top_mm", 48), ("default_font_size_pt", 18),
    ("include_brand_header", False), ("brand_logo_asset_id", uuid4()),
    ("cover_page_enabled", True), ("cover_page", {"title": "Changed"}),
    ("address_blocks", [{"text": "Changed address"}]),
])
def test_changed_layout_or_branding_settings_denied(field, value):
    db, candidate, persisted, tenant = case()
    setattr(persisted, field, value)
    with pytest.raises(PermissionError, match="Letter rendering inputs changed"):
        lock_current_letter_source(
            db=db, document=candidate, authenticated_tenant_id=tenant,
        )
