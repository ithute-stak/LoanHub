#!/usr/bin/env python3
"""Static release validation for LoanHub.

This script does not modify the database. It validates model mapping, the
Alembic graph, route registration, OpenAPI generation, and audit-field safety.
"""

from __future__ import annotations

from pathlib import Path
import ast
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.routing import APIRoute
from sqlalchemy.orm import ColumnProperty, configure_mappers


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def validate_migrations() -> str:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    if len(heads) != 1:
        raise RuntimeError(
            f"Expected one Alembic head, found {len(heads)}: {heads}"
        )

    revisions = list(script.walk_revisions())
    revision_ids = [item.revision for item in revisions]

    if len(revision_ids) != len(set(revision_ids)):
        raise RuntimeError("Duplicate Alembic revision IDs were found")

    return heads[0]


def validate_models() -> tuple[int, int]:
    import database.models  # noqa: F401
    from database.base import Base

    configure_mappers()

    collisions: list[str] = []
    audit_fields = (
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    for mapper in Base.registry.mappers:
        for field in audit_fields:
            mapped_property = mapper.attrs.get(field)

            if not isinstance(mapped_property, ColumnProperty):
                collisions.append(
                    f"{mapper.class_.__name__}.{field}"
                )

    if collisions:
        raise RuntimeError(
            "Audit column/relationship collisions: "
            + ", ".join(sorted(collisions))
        )

    # Forces SQLAlchemy to resolve dependency order. This detects unresolved
    # model cycles unless they are intentionally declared with use_alter.
    sorted_tables = Base.metadata.sorted_tables

    return len(Base.registry.mappers), len(sorted_tables)


def validate_router_registration() -> int:
    router_directory = PROJECT_ROOT / "routers"
    expected_modules = {
        path.stem
        for path in router_directory.glob("*.py")
        if path.stem != "__init__"
    }

    router_source = (
        PROJECT_ROOT / "api" / "v1" / "router.py"
    ).read_text()
    tree = ast.parse(router_source)

    included_modules: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function = node.func

        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "include_router"
            and node.args
        ):
            continue

        argument = node.args[0]

        if (
            isinstance(argument, ast.Attribute)
            and argument.attr == "router"
            and isinstance(argument.value, ast.Name)
        ):
            included_modules.add(argument.value.id)

    missing = sorted(expected_modules - included_modules)
    unknown = sorted(included_modules - expected_modules)

    if missing or unknown:
        raise RuntimeError(
            "Router registration mismatch. "
            f"Missing: {missing}; unknown: {unknown}"
        )

    return len(included_modules)


def validate_routes() -> tuple[int, int]:
    from main import app

    schema = app.openapi()
    seen_routes: dict[tuple[str, str], str] = {}
    seen_operation_ids: dict[str, tuple[str, str]] = {}
    operation_count = 0

    for route in app.routes:
        # Newer FastAPI versions may retain included routers lazily, so OpenAPI
        # is the authoritative flattened route inventory.
        if isinstance(route, APIRoute):
            route.path

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            method_upper = method.upper()

            if method_upper not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
            }:
                continue

            operation_count += 1
            route_key = (method_upper, path)
            operation_id = operation.get("operationId") or ""

            if route_key in seen_routes:
                raise RuntimeError(
                    f"Duplicate route {method_upper} {path}"
                )

            seen_routes[route_key] = operation_id

            if operation_id:
                if operation_id in seen_operation_ids:
                    previous = seen_operation_ids[operation_id]
                    raise RuntimeError(
                        "Duplicate OpenAPI operation ID "
                        f"{operation_id}: {previous} and {route_key}"
                    )

                seen_operation_ids[operation_id] = route_key

    return len(schema["paths"]), operation_count


def main() -> None:
    head = validate_migrations()
    mapper_count, table_count = validate_models()
    router_count = validate_router_registration()
    path_count, operation_count = validate_routes()

    print("LoanHub release validation passed")
    print(f"Alembic head: {head}")
    print(f"SQLAlchemy mappers: {mapper_count}")
    print(f"Database tables: {table_count}")
    print(f"Registered router modules: {router_count}")
    print(f"OpenAPI paths: {path_count}")
    print(f"HTTP operations: {operation_count}")


if __name__ == "__main__":
    main()
