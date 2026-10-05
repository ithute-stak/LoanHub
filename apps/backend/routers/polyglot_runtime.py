from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.access_control import require_platform_admin
from database.models.user import User
from database.session import get_db
from services.polyglot_benchmark_service import (
    list_benchmark_history,
    persist_benchmark_run,
    run_polyglot_benchmarks,
)
from services.polyglot_runtime_service import (
    routing_snapshot,
    runtime_metrics,
    worker_statuses,
)


router = APIRouter(prefix="/runtime", tags=["Runtime"])


@router.get("/workers/status")
def worker_runtime_status(_: User = Depends(require_platform_admin)):
    statuses = worker_statuses()
    return {
        "authority": "python",
        "frontend": ["nextjs", "typescript", "rust_wasm_optional"],
        "backend": ["python", "rust_optional", "go_optional", "java_optional", "cpp_optional"],
        "workers": [
            {
                "name": item.name,
                "configured": item.configured,
                "ready": item.ready,
                "detail": item.detail,
            }
            for item in statuses
        ],
        "runtime_metrics": runtime_metrics(),
        "routing": routing_snapshot(),
        "rules": {
            "loan_decisions": "python_authoritative",
            "accounting": "python_authoritative",
            "experian_writes": "python_authoritative",
            "cdas_writes": "python_authoritative",
            "worker_failure_mode": "python_fallback_for_delegated_safe_work",
        },
    }


@router.post("/benchmarks/run")
def run_runtime_benchmarks(
    iterations: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
):
    benchmark = run_polyglot_benchmarks(iterations=iterations)
    record = persist_benchmark_run(
        db,
        requested_by_user_id=current_user.id,
        benchmark=benchmark,
        routing=routing_snapshot(),
    )
    return {
        **benchmark,
        "history_id": str(record.id),
        "recorded_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/benchmarks/history")
def runtime_benchmark_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return {"items": list_benchmark_history(db, limit=limit)}
