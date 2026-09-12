from core.error_response import build_error_response_content


def test_development_response_contains_real_error():
    content = build_error_response_content(
        error=RuntimeError("document insert failed"),
        request_id="request-123",
        stack="traceback-body",
        environment="development",
        expose_error_details=False,
    )

    assert content["detail"] == "RuntimeError: document insert failed"
    assert content["error_type"] == "RuntimeError"
    assert content["error_message"] == "document insert failed"
    assert content["stack_trace"] == "traceback-body"
    assert content["request_id"] == "request-123"


def test_production_response_hides_real_error():
    content = build_error_response_content(
        error=RuntimeError("database password leaked"),
        request_id="request-456",
        stack="secret traceback",
        environment="production",
        expose_error_details=False,
    )

    assert content == {
        "detail": (
            "The action could not be completed. "
            "The platform owner has been notified."
        ),
        "request_id": "request-456",
    }


def test_explicit_flag_exposes_error_in_any_environment():
    content = build_error_response_content(
        error=ValueError("invalid document payload"),
        request_id="request-789",
        stack="value traceback",
        environment="production",
        expose_error_details=True,
    )

    assert content["detail"] == "ValueError: invalid document payload"
    assert content["request_id"] == "request-789"
