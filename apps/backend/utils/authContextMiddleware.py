from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from utils.convex import (
    current_impersonator_id,
    current_ip_address,
    current_request_id,
    current_user_agent,
    current_user_id,
)
from utils.decode_encode_token import decode_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID') or uuid4().hex
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get('user-agent')

        tokens = [
            (current_user_id, current_user_id.set(None)),
            (current_impersonator_id, current_impersonator_id.set(None)),
            (current_request_id, current_request_id.set(request_id)),
            (current_ip_address, current_ip_address.set(client_ip)),
            (current_user_agent, current_user_agent.set(user_agent)),
        ]
        try:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.partition(' ')[2].strip()
                try:
                    payload = decode_token(token)
                    user_id = payload.get('user_id')
                    if user_id:
                        current_user_id.set(str(user_id))
                    impersonated_by = payload.get('impersonated_by')
                    if impersonated_by:
                        current_impersonator_id.set(str(impersonated_by))
                except Exception:
                    pass

            response = await call_next(request)
            response.headers['X-Request-ID'] = request_id
            return response
        finally:
            for variable, token in reversed(tokens):
                variable.reset(token)
