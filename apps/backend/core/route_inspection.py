from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

try:
    # FastAPI 0.139+ keeps included routers as deferred route groups.
    # This public helper yields effective routes with all include prefixes applied.
    from fastapi.routing import iter_route_contexts as _iter_route_contexts
except ImportError:  # FastAPI <= 0.138
    _iter_route_contexts = None


def iter_effective_routes(source: Any) -> Iterator[Any]:
    """Yield effective routes across supported FastAPI router models.

    FastAPI 0.139 changed ``include_router()`` to retain nested router groups
    instead of eagerly flattening them into ``app.routes``. Older LoanHub code
    and tests inspected ``app.routes`` directly, which makes real routes appear
    missing on 0.139+. This adapter uses FastAPI's public route-context iterator
    when available and falls back to the older flat route list otherwise.
    """

    routes = getattr(source, "routes", source)
    if routes is None:
        return

    if _iter_route_contexts is not None:
        yield from _iter_route_contexts(routes)
        return

    yield from routes


def iter_http_route_pairs(source: Any) -> Iterator[tuple[str, str]]:
    """Yield normalized HTTP ``(method, path)`` pairs for a router/app."""

    for route in iter_effective_routes(source):
        path = getattr(route, "path", None)
        if not path:
            continue
        for method in getattr(route, "methods", set()) or set():
            method_name = str(method).upper()
            if method_name in {"HEAD", "OPTIONS"}:
                continue
            yield method_name, path


def methods_for_path(source: Any, path: str) -> set[str]:
    return {
        method
        for method, route_path in iter_http_route_pairs(source)
        if route_path == path
    }


def find_http_route(source: Any, path: str, method: str) -> Any | None:
    expected_method = method.upper()
    for route in iter_effective_routes(source):
        if getattr(route, "path", None) != path:
            continue
        methods = {
            str(value).upper()
            for value in (getattr(route, "methods", set()) or set())
        }
        if expected_method in methods:
            return route
    return None


def validate_http_route_contracts(
    source: Any,
    *,
    required: Iterable[tuple[str, str]] = (),
) -> None:
    """Fail fast on missing critical routes or duplicate method/path pairs.

    Validation is intentionally performed against the final FastAPI application,
    not an intermediate APIRouter. That makes the check accurate for both the old
    eager-flattening implementation and FastAPI 0.139+'s deferred router groups.
    """

    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for pair in iter_http_route_pairs(source):
        if pair in seen:
            duplicates.add(pair)
        seen.add(pair)

    if duplicates:
        values = ", ".join(f"{method} {path}" for method, path in sorted(duplicates))
        raise RuntimeError(f"Duplicate LoanHub API routes detected: {values}")

    normalized_required = {(method.upper(), path) for method, path in required}
    missing = normalized_required - seen
    if missing:
        values = ", ".join(f"{method} {path}" for method, path in sorted(missing))
        raise RuntimeError(f"Critical LoanHub API routes are missing: {values}")
