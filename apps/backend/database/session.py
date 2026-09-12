import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.config.config import settings


def _json_default(value):
    """Convert values commonly produced by financial/domain code into JSON-safe primitives."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def json_serializer(value) -> str:
    """Serialize PostgreSQL JSON/JSONB values without losing Decimal precision."""
    return json.dumps(value, default=_json_default)


# SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # ensures broken connections are recycled
    json_serializer=json_serializer,
)

# Session local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        # LelefaPayGate operational configuration is database-owned. Refresh
        # the compatibility runtime cache for each request so Super Admin
        # changes become effective across workers without editing .env files.
        from services.lelefa_paygate_config_service import synchronize_runtime_settings

        synchronize_runtime_settings(db)
        yield db
    finally:
        db.close()
