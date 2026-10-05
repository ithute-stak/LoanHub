from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _scalar(db: Session, sql: str, params: dict | None = None, default=None):
    value = db.execute(text(sql), params or {}).scalar()
    return default if value is None else value


def database_health_snapshot(db: Session) -> dict[str, Any]:
    """Read-only PostgreSQL health/tuning snapshot for Platform Owner.

    The queries intentionally use PostgreSQL system catalogs/statistics only.
    No tuning or recovery action is executed from this endpoint.
    """
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect != "postgresql":
        return {
            "database_engine": dialect or "unknown",
            "supported": False,
            "message": "Detailed database management telemetry is available for PostgreSQL.",
        }

    database_name = str(_scalar(db, "SELECT current_database()", default=""))
    database_size = int(
        _scalar(db, "SELECT pg_database_size(current_database())", default=0)
    )
    max_connections = int(
        _scalar(db, "SELECT current_setting('max_connections')::int", default=0)
    )

    activity = db.execute(
        text(
            """
            SELECT
                count(*) FILTER (WHERE state = 'active') AS active_connections,
                count(*) FILTER (WHERE state = 'idle') AS idle_connections,
                count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_transaction,
                count(*) FILTER (
                    WHERE xact_start IS NOT NULL
                      AND now() - xact_start > interval '60 seconds'
                ) AS long_transactions,
                COALESCE(
                    max(EXTRACT(EPOCH FROM (now() - xact_start)))
                    FILTER (WHERE xact_start IS NOT NULL),
                    0
                ) AS oldest_transaction_seconds,
                count(*) FILTER (
                    WHERE cardinality(pg_blocking_pids(pid)) > 0
                ) AS blocked_sessions
            FROM pg_stat_activity
            WHERE datname = current_database()
            """
        )
    ).mappings().one()

    stats = db.execute(
        text(
            """
            SELECT
                xact_commit,
                xact_rollback,
                deadlocks,
                blks_read,
                blks_hit,
                temp_files,
                temp_bytes,
                tup_returned,
                tup_fetched,
                tup_inserted,
                tup_updated,
                tup_deleted,
                stats_reset
            FROM pg_stat_database
            WHERE datname = current_database()
            """
        )
    ).mappings().one()

    blks_hit = int(stats["blks_hit"] or 0)
    blks_read = int(stats["blks_read"] or 0)
    cache_total = blks_hit + blks_read
    cache_hit_percent = (
        round((blks_hit / cache_total) * 100, 3) if cache_total else 100.0
    )

    tables = [
        dict(row)
        for row in db.execute(
            text(
                """
                SELECT
                    s.relname AS table_name,
                    pg_total_relation_size(s.relid) AS total_bytes,
                    pg_relation_size(s.relid) AS table_bytes,
                    pg_indexes_size(s.relid) AS index_bytes,
                    s.n_live_tup,
                    s.n_dead_tup,
                    s.seq_scan,
                    s.idx_scan,
                    s.n_tup_ins,
                    s.n_tup_upd,
                    s.n_tup_del,
                    s.last_analyze,
                    s.last_autoanalyze,
                    s.last_autovacuum
                FROM pg_stat_user_tables s
                ORDER BY pg_total_relation_size(s.relid) DESC
                LIMIT 20
                """
            )
        ).mappings().all()
    ]

    indexes = [
        dict(row)
        for row in db.execute(
            text(
                """
                SELECT
                    t.relname AS table_name,
                    i.indexrelname AS index_name,
                    i.idx_scan,
                    pg_relation_size(i.indexrelid) AS index_bytes
                FROM pg_stat_user_indexes i
                JOIN pg_class t ON t.oid = i.relid
                ORDER BY pg_relation_size(i.indexrelid) DESC
                LIMIT 30
                """
            )
        ).mappings().all()
    ]

    constraints = [
        dict(row)
        for row in db.execute(
            text(
                """
                SELECT
                    c.conname AS constraint_name,
                    c.conrelid::regclass::text AS table_name,
                    pg_get_constraintdef(c.oid) AS definition
                FROM pg_constraint c
                WHERE c.contype = 'c'
                  AND c.convalidated = false
                  AND c.connamespace = 'public'::regnamespace
                ORDER BY c.conrelid::regclass::text, c.conname
                """
            )
        ).mappings().all()
    ]

    alembic_heads = [
        str(row[0])
        for row in db.execute(text("SELECT version_num FROM alembic_version")).all()
    ]

    replication = {
        "is_replica": bool(_scalar(db, "SELECT pg_is_in_recovery()", default=False)),
        "connected_replicas": int(
            _scalar(db, "SELECT count(*) FROM pg_stat_replication", default=0)
        ),
    }

    runtime_role = dict(
        db.execute(
            text(
                """
                SELECT
                    rolname AS role_name,
                    rolsuper AS is_superuser,
                    rolbypassrls AS row_security_override
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
        ).mappings().one()
    )

    row_security_tables = [
        dict(row)
        for row in db.execute(
            text(
                """
                SELECT
                    n.nspname AS schema_name,
                    c.relname AS table_name,
                    pg_get_userbyid(c.relowner) AS table_owner,
                    c.relrowsecurity AS enabled,
                    c.relforcerowsecurity AS forced,
                    count(p.policyname) AS policy_count
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_policies p
                  ON p.schemaname = n.nspname
                 AND p.tablename = c.relname
                WHERE c.relkind IN ('r', 'p')
                  AND c.relrowsecurity = true
                  AND n.nspname = 'public'
                GROUP BY
                    n.nspname,
                    c.relname,
                    c.relowner,
                    c.relrowsecurity,
                    c.relforcerowsecurity
                ORDER BY c.relname
                """
            )
        ).mappings().all()
    ]

    runtime_role_name = str(runtime_role["role_name"])
    runtime_owns_protected_table = any(
        str(row["table_owner"]) == runtime_role_name
        for row in row_security_tables
    )
    tables_without_policy = [
        str(row["table_name"])
        for row in row_security_tables
        if int(row["policy_count"] or 0) == 0
    ]
    row_security = {
        "runtime_role": runtime_role_name,
        "runtime_is_superuser": bool(runtime_role["is_superuser"]),
        "runtime_has_override": bool(runtime_role["row_security_override"]),
        "runtime_owns_protected_table": runtime_owns_protected_table,
        "protected_table_count": len(row_security_tables),
        "tables_without_policy": tables_without_policy,
        "tables": row_security_tables,
        "enforcement_ready": bool(row_security_tables)
        and not bool(runtime_role["is_superuser"])
        and not bool(runtime_role["row_security_override"])
        and not runtime_owns_protected_table
        and not tables_without_policy,
    }

    return {
        "supported": True,
        "database_engine": "postgresql",
        "database_name": database_name,
        "database_size_bytes": database_size,
        "connections": {
            "max": max_connections,
            "active": int(activity["active_connections"] or 0),
            "idle": int(activity["idle_connections"] or 0),
            "idle_in_transaction": int(activity["idle_in_transaction"] or 0),
        },
        "transactions": {
            "commits": int(stats["xact_commit"] or 0),
            "rollbacks": int(stats["xact_rollback"] or 0),
            "deadlocks": int(stats["deadlocks"] or 0),
            "long_running_over_60s": int(activity["long_transactions"] or 0),
            "oldest_seconds": float(activity["oldest_transaction_seconds"] or 0),
            "blocked_sessions": int(activity["blocked_sessions"] or 0),
        },
        "io": {
            "blocks_read": blks_read,
            "blocks_hit": blks_hit,
            "cache_hit_percent": cache_hit_percent,
            "temp_files": int(stats["temp_files"] or 0),
            "temp_bytes": int(stats["temp_bytes"] or 0),
        },
        "tuple_activity": {
            "returned": int(stats["tup_returned"] or 0),
            "fetched": int(stats["tup_fetched"] or 0),
            "inserted": int(stats["tup_inserted"] or 0),
            "updated": int(stats["tup_updated"] or 0),
            "deleted": int(stats["tup_deleted"] or 0),
        },
        "stats_reset": stats["stats_reset"],
        "replication": replication,
        "row_security": row_security,
        "alembic_heads": alembic_heads,
        "unvalidated_check_constraints": constraints,
        "largest_tables": tables,
        "largest_indexes": indexes,
    }
