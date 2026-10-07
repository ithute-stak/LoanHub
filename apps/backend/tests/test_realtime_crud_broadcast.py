from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "apps" / "backend"
FRONTEND = ROOT / "apps" / "frontend"


def test_database_events_are_commit_only_and_rollback_safe() -> None:
    source = (BACKEND / "core" / "transparency.py").read_text(encoding="utf-8")

    assert '"event_id": str(uuid.uuid4())' in source
    assert '"type": "DB_EVENT"' in source
    assert '"contract": "loanhub.db-commit.v1"' in source
    assert '@event.listens_for(Session, "after_commit")' in source
    assert 'session.info.pop("loanhub_db_commit_events", [])' in source
    assert '@event.listens_for(Session, "after_rollback")' in source
    assert 'session.info.pop("loanhub_db_commit_events", None)' in source
    assert 'await manager.send_to_channel(channel, payload)' in source


def test_normal_and_bulk_database_writes_are_broadcast() -> None:
    source = (BACKEND / "core" / "transparency.py").read_text(encoding="utf-8")

    assert '@event.listens_for(Session, "before_flush")' in source
    assert '@event.listens_for(Session, "do_orm_execute")' in source
    assert 'getattr(execute_state, "is_insert", False)' in source
    assert 'getattr(execute_state, "is_update", False)' in source
    assert 'getattr(execute_state, "is_delete", False)' in source
    assert '"bulk": True' in source


def test_realtime_scope_does_not_broadcast_record_contents() -> None:
    source = (BACKEND / "core" / "transparency.py").read_text(encoding="utf-8")
    commit_start = source.index('commit_events.append({')
    commit_end = source.index('audit_id = uuid.uuid4()', commit_start)
    commit_payload = source[commit_start:commit_end]

    assert '"company_id"' in commit_payload
    assert '"branch_id"' in commit_payload
    assert '"changed_fields"' in commit_payload
    assert '"before"' not in commit_payload
    assert '"after"' not in commit_payload
    assert '"password"' not in commit_payload
    assert '{"platform"}' in commit_payload
    assert 'f"company-{company_id}"' in commit_payload


def test_platform_roles_subscribe_to_shared_database_channel() -> None:
    source = (BACKEND / "routers" / "ws.py").read_text(encoding="utf-8")

    assert "PLATFORM_ROLES" in source
    assert "if user.role in PLATFORM_ROLES:" in source
    assert "channels.add('platform')" in source


def test_frontend_batches_commit_events_and_catches_up_after_reconnect() -> None:
    realtime = (FRONTEND / "provider" / "realtimeProvider.tsx").read_text(
        encoding="utf-8"
    )
    boundary = (FRONTEND / "provider" / "realtimeScreenBoundary.tsx").read_text(
        encoding="utf-8"
    )
    providers = (FRONTEND / "provider" / "providers.tsx").read_text(
        encoding="utf-8"
    )

    assert 'String(payload.type ?? "") === "DB_EVENT"' in realtime
    assert "pendingDbEventsRef" in realtime
    assert "dbBatchStartedAtRef" in realtime
    assert "2_000" in realtime
    assert "750 - elapsed" in realtime
    assert "new Map(" in realtime
    assert "receivedCount" in realtime
    assert "hasRemoteChanges" in realtime
    assert "shouldRefreshRouteForCommit(pathname, detailForDispatch)" in realtime
    assert "cacheTagsForResources(resources)" in realtime
    assert "cacheTagsInvalidated({ scope, tags })" in realtime
    assert "beginRealtimeCatchupWindow" in realtime
    assert "reconnect_catchup" in realtime
    assert "router.refresh()" in realtime
    assert "DB_COMMIT_EVENT_NAME" in boundary
    assert "userIsEditing()" in boundary
    assert "pendingRef.current = true" in boundary
    assert "shouldRefreshRouteForCommit(pathname, detail)" in boundary
    assert "<RealtimeScreenBoundary>{children}</RealtimeScreenBoundary>" in providers


def test_local_mutation_echoes_are_identified_and_realtime_reads_bypass_cache() -> None:
    api = (FRONTEND / "lib" / "api.ts").read_text(encoding="utf-8")
    commit = (FRONTEND / "lib" / "realtime-commit.ts").read_text(encoding="utf-8")

    assert 'config.headers["X-Request-ID"] = requestId' in api
    assert "rememberLocalMutationRequest(requestId)" in api
    assert "shouldBypassCacheForRealtime()" in api
    assert 'config.headers["X-LoanHub-Cache"] = "bypass"' in api
    assert "RECENT_REQUEST_TTL_MS" in commit
    assert "beginRealtimeCatchupWindow" in commit


def test_shared_collections_refresh_only_affected_resources_and_sort_deterministically() -> None:
    provider = (FRONTEND / "provider" / "appDataProvider.tsx").read_text(
        encoding="utf-8"
    )
    resources = (FRONTEND / "lib" / "realtime-resources.ts").read_text(
        encoding="utf-8"
    )
    sorting = (FRONTEND / "lib" / "stable-sort.ts").read_text(encoding="utf-8")

    assert "resourcesForCommitBatch(detail)" in provider
    assert "refreshRealtimeResources(batch)" in provider
    assert 'resources.has("loans")' in provider
    assert 'resources.has("payments")' in provider
    assert 'resources.has("billing")' in provider
    assert "deletedEntityIdsByResource(detail)" in provider
    assert "window.addEventListener(DB_COMMIT_EVENT_NAME, onDatabaseCommit)" in provider

    assert "TABLE_RESOURCES" in resources
    assert "SAFE_DELETE_RESOURCE" in resources
    assert 'payment_transactions: ["payments", "loans"]' in resources
    assert 'payment_transactions: "payments"' in resources
    assert "shouldRefreshRouteForCommit" in resources
    assert "RESOURCE_CACHE_TAGS" in resources
    assert "cacheTagsForResources" in resources
    assert "Unknown tables are safer to refresh" in resources

    assert "stableSmartSort" in provider
    assert "newest first" in sorting
    assert "localeCompare" in sorting
    assert "return left.index - right.index" in sorting
