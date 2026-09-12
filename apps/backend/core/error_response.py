from __future__ import annotations


def should_expose_error_details(
    *,
    environment: str | None,
    expose_error_details: bool,
) -> bool:
    normalized = (environment or "").strip().lower()
    return expose_error_details or normalized in {
        "development",
        "dev",
        "local",
        "test",
        "testing",
    }


def build_error_response_content(
    *,
    error: Exception,
    request_id: str,
    stack: str,
    environment: str | None,
    expose_error_details: bool,
) -> dict[str, object]:
    if should_expose_error_details(
        environment=environment,
        expose_error_details=expose_error_details,
    ):
        message = str(error).strip() or "Unhandled application error"
        return {
            "detail": f"{type(error).__name__}: {message}",
            "request_id": request_id,
            "error_type": type(error).__name__,
            "error_message": message,
            "stack_trace": stack[-12000:],
        }

    return {
        "detail": (
            "The action could not be completed. "
            "The platform owner has been notified."
        ),
        "request_id": request_id,
    }
