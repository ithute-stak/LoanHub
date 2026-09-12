from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v1.router import api_router
import core.audit_integrity  # noqa: F401 - seals immutable audit events
import core.transparency  # noqa: F401 - registers SQLAlchemy transparency listeners
from core.error_monitoring import SystemErrorMonitoringMiddleware
from core.observability import install_observability
from core.response_cache import (
    TenantResponseCacheMiddleware,
    response_cache,
)
from core.security_middleware import SecurityControlMiddleware
from core.websocket_manager import manager
from core.route_inspection import validate_http_route_contracts
from database.config.config import settings
from database.session import SessionLocal, get_db
from utils.authContextMiddleware import AuthContextMiddleware
from services.employer_group_service import ensure_central_work_groups
from services.maturity_recovery_scheduler import (
    start_maturity_recovery_scheduler,
    stop_maturity_recovery_scheduler,
)
from services.treasury_scheduler import start_treasury_scheduler, stop_treasury_scheduler
from services.webhook_outbox_scheduler import start_webhook_outbox_scheduler, stop_webhook_outbox_scheduler


def _seed_central_work_groups() -> None:
    """Ensure the canonical LoanHub work-group catalogue exists before serving."""
    db = SessionLocal()
    try:
        try:
            ensure_central_work_groups(db)
        except IntegrityError:
            # Multiple web workers can start together on a fresh installation.
            # If another worker wins the unique-code insert race, roll back and
            # re-run the idempotent repair against the now-persisted catalogue.
            db.rollback()
            ensure_central_work_groups(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start production workers normally and keep sandbox side effects disabled."""
    treasury_started = False
    maturity_started = False
    webhook_started = False
    _seed_central_work_groups()
    await manager.start()
    try:
        # The public sandbox is intentionally writable but must never launch
        # background jobs that can attempt real payouts, webhook deliveries or
        # scheduled lifecycle actions. Its Docker network is also internal-only.
        if not settings.SANDBOX_MODE:
            # Maturity/collections timing is a core lending invariant rather than an
            # optional treasury feature. It runs every minute; the service itself
            # uses a PostgreSQL advisory transaction lock and deduplication keys so
            # multiple web workers remain safe.
            await start_maturity_recovery_scheduler(60)
            maturity_started = True
            await start_webhook_outbox_scheduler(10)
            webhook_started = True
            if settings.TREASURY_AUTO_SUBMIT_ENABLED:
                await start_treasury_scheduler(settings.TREASURY_AUTO_SUBMIT_INTERVAL_SECONDS)
                treasury_started = True
        yield
    finally:
        if treasury_started:
            await stop_treasury_scheduler()
        if maturity_started:
            await stop_maturity_recovery_scheduler()
        if webhook_started:
            await stop_webhook_outbox_scheduler()
        await response_cache.close()
        await manager.shutdown()


app = FastAPI(
    title="LoanHub API",
    version="2.0.0",
    description=(
        "Secure multi-tenant loan marketplace, management, accounting, "
        "reporting, files and realtime communication platform"
    ),
    lifespan=lifespan,
)

install_observability(app)
app.add_middleware(SystemErrorMonitoringMiddleware)
app.add_middleware(SecurityControlMiddleware)
# AuthContext must wrap the response cache so cache keys can use the verified
# user context without decoding or storing access tokens.
app.add_middleware(TenantResponseCacheMiddleware)
app.add_middleware(AuthContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "X-Company-ID",
        "X-Request-ID",
        "X-Active-Role",
        "X-LoanHub-Cache",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-LoanHub-Client-Cache",
        "X-LoanHub-Server-Cache",
    ],
    max_age=3600,
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["System"])
def root():
    return {
        "message": "LoanHub API is running",
        "environment": settings.ENVIRONMENT,
        "sandbox": settings.SANDBOX_MODE,
    }


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "healthy"}


# LoanHub initial super-admin bootstrap
from services.bootstrap_superadmin import install_superadmin_bootstrap

install_superadmin_bootstrap(app)

_CRITICAL_API_ROUTES = {
    ("GET", "/api/v1/analytics/company"),
    ("GET", "/api/v1/analytics/platform"),
    ("GET", "/api/v1/analytics/borrower"),
    ("POST", "/api/v1/loans/calculator"),
    ("GET", "/api/v1/system-updates/status"),
    ("POST", "/api/v1/system-updates/update"),
}

# Validate the final application route graph after all nested router prefixes
# have been applied. This is compatible with FastAPI's deferred router model.
validate_http_route_contracts(app, required=_CRITICAL_API_ROUTES)
