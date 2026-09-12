from contextvars import ContextVar


current_user_id = ContextVar('current_user_id', default=None)
current_impersonator_id = ContextVar('current_impersonator_id', default=None)
current_request_id = ContextVar('current_request_id', default=None)
current_ip_address = ContextVar('current_ip_address', default=None)
current_user_agent = ContextVar('current_user_agent', default=None)
