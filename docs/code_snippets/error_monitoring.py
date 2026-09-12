from __future__ import annotations

import hashlib
import traceback
import uuid
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.websocket_manager import manager
from database.config.config import settings
from database.models.audit_log import AuditLog
from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType, UserRole
from database.models.notification import Notification
from database.models.system_error import SystemErrorLog
from database.models.user import User
from database.session import SessionLocal
from utils.convex import current_user_id


def _uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _trusted_tenant_scope(db, user_id: UUID | None, requested_company_id: UUID | None):
    if not user_id:
        return None, None
    query = db.query(CompanyStaff).filter(
        CompanyStaff.user_id == user_id,
        CompanyStaff.is_active.is_(True),
    )
    if requested_company_id:
        query = query.filter(CompanyStaff.company_id == requested_company_id)
    membership = query.order_by(CompanyStaff.created_at.asc()).first()
    if not membership:
        return None, None
    return membership.company_id, membership.branch_id


class SystemErrorMonitoringMiddleware(BaseHTTPMiddleware):
    """Capture unhandled failures without exposing diagnostics to ordinary users.

    The affected user receives one generic response containing a request ID.
    Only active platform owners receive the technical incident notification.
    Recurring fingerprints are grouped and rate-limited to avoid inbox spam.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        try:
            response = await call_next(request)
            response.headers['X-Request-ID'] = request_id
            return response
        except Exception as error:
            stack = traceback.format_exc()
            fingerprint = hashlib.sha256(
                (
                    f'{request.method}:{request.url.path}:'
                    f'{type(error).__name__}:{str(error)[:500]}'
                ).encode()
            ).hexdigest()

            user_id = _uuid(current_user_id.get())
            requested_company_id = _uuid(request.headers.get('X-Company-ID'))
            realtime_payloads: list[dict] = []
            db = SessionLocal()
            try:
                company_id, branch_id = _trusted_tenant_scope(
                    db,
                    user_id,
                    requested_company_id,
                )
                log = db.query(SystemErrorLog).filter(
                    SystemErrorLog.fingerprint == fingerprint
                ).first()
                was_resolved = bool(log and log.is_resolved)
                is_new = log is None

                if log:
                    log.occurrence_count += 1
                    log.last_seen_at = datetime.utcnow()
                    log.request_id = request_id
                    log.user_id = user_id
                    log.company_id = company_id
                    log.branch_id = branch_id
                    log.message = str(error)[:4000]
                    log.stack_trace = stack[-20000:]
                    log.user_agent = request.headers.get('user-agent')
                    log.is_resolved = False
                    log.resolved_at = None
                    log.resolved_by_user_id = None
                    log.resolution_notes = None
                else:
                    log = SystemErrorLog(
                        request_id=request_id,
                        fingerprint=fingerprint,
                        user_id=user_id,
                        company_id=company_id,
                        branch_id=branch_id,
                        method=request.method,
                        path=request.url.path,
                        status_code=500,
                        error_type=type(error).__name__,
                        message=str(error)[:4000] or 'Unhandled application error',
                        stack_trace=stack[-20000:],
                        severity='critical',
                        environment=settings.ENVIRONMENT,
                        user_agent=request.headers.get('user-agent'),
                        context={
                            'query': dict(request.query_params),
                            'client': request.client.host if request.client else None,
                        },
                    )
                    db.add(log)
                    db.flush()

                db.add(AuditLog(
                    user_id=user_id,
                    company_id=company_id,
                    branch_id=branch_id,
                    action='created' if is_new else 'updated',
                    table_name='system_error_logs',
                    entity_type='system_error_logs',
                    record_id=log.id,
                    description=(
                        'A new system error was captured.'
                        if is_new
                        else 'A recurring system error was captured.'
                    ),
                    actor_role=None,
                    severity='critical',
                    status='failure',
                    before_data={},
                    after_data={
                        'occurrence_count': log.occurrence_count,
                        'is_resolved': False,
                        'path': log.path,
                        'error_type': log.error_type,
                    },
                    changed_fields=[] if is_new else ['occurrence_count', 'last_seen_at', 'is_resolved'],
                    event_data={
                        'automatic': True,
                        'request_id': request_id,
                        'fingerprint': fingerprint,
                    },
                    request_id=request_id,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get('user-agent'),
                ))

                recent_cutoff = datetime.utcnow() - timedelta(minutes=15)
                recent_notification_exists = db.query(Notification.id).filter(
                    Notification.entity_type == 'system_error_logs',
                    Notification.entity_id == str(log.id),
                    Notification.created_at >= recent_cutoff,
                ).first() is not None

                if is_new or was_resolved or not recent_notification_exists:
                    platform_owners = db.query(User.id).filter(
                        User.role == UserRole.SUPERADMIN,
                        User.is_active.is_(True),
                    ).all()
                    for (admin_id,) in platform_owners:
                        notification = Notification(
                            user_id=admin_id,
                            actor_user_id=user_id,
                            company_id=company_id,
                            branch_id=branch_id,
                            title='System error detected',
                            message=(
                                f'{request.method} {request.url.path} failed. '
                                f'Request reference: {request_id}.'
                            ),
                            notification_type=NotificationType.SYSTEM,
                            entity_type='system_error_logs',
                            entity_id=str(log.id),
                            action_url='/superadmin/system-errors',
                            action_label='Investigate error',
                            icon='triangle-alert',
                            priority='critical',
                            data={
                                'request_id': request_id,
                                'fingerprint': fingerprint,
                                'error_type': log.error_type,
                                'occurrence_count': log.occurrence_count,
                            },
                        )
                        db.add(notification)
                        db.flush()
                        realtime_payloads.append({
                            'type': 'NOTIFICATION_CREATED',
                            'user_id': str(admin_id),
                            'notification': {
                                'id': str(notification.id),
                                'title': notification.title,
                                'message': notification.message,
                                'notification_type': notification.notification_type.value,
                                'action_url': notification.action_url,
                                'action_label': notification.action_label,
                                'icon': notification.icon,
                                'priority': notification.priority,
                                'is_read': False,
                                'created_at': notification.created_at.isoformat() if notification.created_at else datetime.utcnow().isoformat(),
                            },
                        })

                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()

            for payload in realtime_payloads:
                try:
                    await manager.send_to_user(payload['user_id'], payload)
                except Exception:
                    pass

            return JSONResponse(
                status_code=500,
                content={
                    'detail': 'The action could not be completed. The platform owner has been notified.',
                    'request_id': request_id,
                },
                headers={'X-Request-ID': request_id},
            )
