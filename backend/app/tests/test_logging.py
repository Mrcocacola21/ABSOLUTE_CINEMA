"""Unit tests for logging redaction helpers."""

from __future__ import annotations

import io
import logging

from app.core.logging import REDACTED_VALUE, RedactingFormatter, sanitize_for_logging


def test_sanitize_for_logging_redacts_sensitive_nested_values() -> None:
    payload = {
        "email": "admin@cinema-showcase.dev",
        "password": "CinemaDemo123!",
        "password_hash": "hashed-secret",
        "nested": {
            "access_token": "jwt-token",
            "Authorization": "Bearer top-secret-token",
        },
        "headers": [
            {"authorization": "Bearer another-secret"},
            {"x-request-id": "req-123"},
        ],
    }

    sanitized = sanitize_for_logging(payload)

    assert sanitized["email"] == "admin@cinema-showcase.dev"
    assert sanitized["password"] == REDACTED_VALUE
    assert sanitized["password_hash"] == REDACTED_VALUE
    assert sanitized["nested"]["access_token"] == REDACTED_VALUE
    assert sanitized["nested"]["Authorization"] == REDACTED_VALUE
    assert sanitized["headers"][0]["authorization"] == REDACTED_VALUE
    assert sanitized["headers"][1]["x-request-id"] == "req-123"


def test_redacting_formatter_masks_sensitive_values_in_emitted_messages() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter("%(message)s"))

    logger = logging.getLogger("test_logging_redaction")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate

    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        logger.info(
            "Authorization: Bearer live-token password=%s token=%s payload=%s",
            "CinemaDemo123!",
            "jwt-token",
            {"secret_key": "super-secret", "safe": "value"},
        )
    finally:
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    output = stream.getvalue()

    assert "live-token" not in output
    assert "CinemaDemo123!" not in output
    assert "jwt-token" not in output
    assert "super-secret" not in output
    assert "Authorization: <redacted>" in output
    assert "password=<redacted>" in output
    assert "token=<redacted>" in output
    assert "'secret_key': '<redacted>'" in output
    assert "'safe': 'value'" in output
