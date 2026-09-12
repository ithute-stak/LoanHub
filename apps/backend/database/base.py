import uuid

from sqlalchemy import Column, DateTime, String, UUID, event, func, inspect
from sqlalchemy.orm import ColumnProperty, declarative_base

from utils.convex import current_user_id


Declaration = declarative_base()


class CustomBase:
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)


class Base(CustomBase, Declaration):
    __abstract__ = True


def get_modified_attributes(target) -> dict:
    """Return changed mapped columns without lazy-loading relationships."""
    state = inspect(target)
    modified: dict = {}

    for column_attribute in state.mapper.column_attrs:
        attribute_name = column_attribute.key
        history = state.attrs[attribute_name].history

        if not history.has_changes():
            continue

        modified[attribute_name] = (
            history.added[0] if history.added else None
        )

    return modified


def _set_audit_column(target, column_name: str, value: str) -> None:
    """Set an audit value only when the mapped attribute is a scalar column.

    A model relationship must never reuse ``created_by`` or ``updated_by``.
    This guard prevents a relationship naming mistake from crashing every
    insert/update operation with ``_sa_instance_state`` errors.
    """
    state = inspect(target)
    mapped_property = state.mapper.attrs.get(column_name)

    if not isinstance(mapped_property, ColumnProperty):
        return

    if not mapped_property.columns:
        return

    setattr(target, column_name, value)


def set_created_by(mapper, connection, target) -> None:
    user_id = current_user_id.get()

    if not user_id:
        return

    value = str(user_id)
    _set_audit_column(target, "created_by", value)
    _set_audit_column(target, "updated_by", value)


def set_updated_by(mapper, connection, target) -> None:
    user_id = current_user_id.get()

    # Evaluate changes without touching relationship properties.
    get_modified_attributes(target)

    if user_id:
        _set_audit_column(target, "updated_by", str(user_id))


event.listen(
    Base,
    "before_insert",
    set_created_by,
    propagate=True,
)

event.listen(
    Base,
    "before_update",
    set_updated_by,
    propagate=True,
)
