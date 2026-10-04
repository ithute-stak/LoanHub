from __future__ import annotations

from fastapi import APIRouter, Depends

from core.access_control import require_platform_admin
from database.models.user import User
from services.polyglot_runtime_service import worker_statuses


router = APIRouter(prefix="/runtime", tags=["Runtime"])


@router.get("/workers/status")
def worker_runtime_status(_: User = Depends(require_platform_admin)):
    statuses = worker_statuses()
    return {
        "authority": "python",
        "frontend": ["nextjs", "typescript", "rust_wasm_optional"],
        "backend": ["python", "rust_optional", "go_optional", "cpp_optional"],
        "workers": [
            {
                "name": item.name,
                "configured": item.configured,
                "ready": item.ready,
                "detail": item.detail,
            }
            for item in statuses
        ],
        "rules": {
            "loan_decisions": "python_authoritative",
            "accounting": "python_authoritative",
            "experian_writes": "python_authoritative",
            "cdas_writes": "python_authoritative",
            "worker_failure_mode": "python_fallback_for_delegated_safe_work",
        },
    }
