import logging

from fastapi.testclient import TestClient

from backend_app.config import get_settings
from backend_app.logging_filters import RedactingFilter
from backend_app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_hold_no_api_key():
    """The server never holds a credential of its own; keys arrive per-request."""
    settings = get_settings()
    assert not hasattr(settings, "openai_api_key")
    assert not hasattr(settings, "api_key")


def test_settings_expose_the_expected_limits():
    settings = get_settings()
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.max_rows == 200_000
    assert settings.default_row_limit == 5000
    assert settings.session_ttl_seconds == 1800


def test_redacting_filter_strips_api_keys_from_messages():
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="calling with sk-proj-abcdef1234567890abcdef", args=(), exc_info=None,
    )
    RedactingFilter().filter(record)
    assert "sk-proj-abcdef1234567890abcdef" not in record.msg
    assert "REDACTED" in record.msg


def test_redacting_filter_strips_api_keys_from_args():
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname="", lineno=0,
        msg="key is %s", args=("sk-proj-abcdef1234567890abcdef",), exc_info=None,
    )
    RedactingFilter().filter(record)
    assert "sk-proj-abcdef1234567890abcdef" not in record.getMessage()


def test_cors_allows_the_api_key_header():
    """The frontend sends X-OpenAI-Key; CORS has to permit it or every ask fails."""
    client = TestClient(create_app())
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-OpenAI-Key",
        },
    )
    assert response.status_code == 200
    allowed = response.headers.get("access-control-allow-headers", "").lower()
    assert "x-openai-key" in allowed
