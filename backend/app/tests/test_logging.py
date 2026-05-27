"""Unit tests for logging redaction helpers."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import (
    REDACTED_VALUE,
    RedactingFormatter,
    configure_logging,
    get_audit_logger,
    get_logger,
    get_payment_logger,
    reset_request_id,
    sanitize_for_logging,
    set_request_id,
)
from app.middleware.request_logging import RequestLoggingMiddleware


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


def test_configure_logging_creates_files_routes_events_and_redacts_extras(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    payments_log = tmp_path / "payments.log"
    audit_log = tmp_path / "audit.log"

    configure_logging(
        "INFO",
        app_log_file=str(app_log),
        payments_log_file=str(payments_log),
        audit_log_file=str(audit_log),
        max_bytes=10_000,
        backup_count=1,
    )

    request_token = set_request_id("req-logging-test")
    try:
        get_logger("tests").info(
            "App event authorization=Bearer app-token",
            extra={"path": "/api/v1/health"},
        )
        get_payment_logger("tests").info(
            "Payment event",
            extra={
                "payment_id": "payment-1",
                "provider_secret": "provider-secret-value",
                "metadata": {"webhook_signature": "signature-secret", "safe": "value"},
            },
        )
        get_audit_logger("tests").warning(
            "Audit event",
            extra={"action": "admin.movie.deleted", "access_token": "admin-token-value"},
        )
    finally:
        reset_request_id(request_token)

    _flush_logging_handlers()

    app_output = app_log.read_text(encoding="utf-8")
    payments_output = payments_log.read_text(encoding="utf-8")
    audit_output = audit_log.read_text(encoding="utf-8")

    assert "request_id=req-logging-test" in app_output
    assert "App event authorization=<redacted>" in app_output
    assert "Payment event" not in app_output
    assert "Audit event" not in app_output
    assert "Payment event" in payments_output
    assert "payment_id=payment-1" in payments_output
    assert "provider-secret-value" not in payments_output
    assert "signature-secret" not in payments_output
    assert "provider_secret=<redacted>" in payments_output
    assert "'webhook_signature': '<redacted>'" in payments_output
    assert "'safe': 'value'" in payments_output
    assert "Audit event" in audit_output
    assert "admin-token-value" not in audit_output
    assert "access_token=<redacted>" in audit_output


def test_repeated_configure_logging_does_not_duplicate_handlers_or_records(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    payments_log = tmp_path / "payments.log"
    audit_log = tmp_path / "audit.log"

    for _ in range(2):
        configure_logging(
            "INFO",
            app_log_file=str(app_log),
            payments_log_file=str(payments_log),
            audit_log_file=str(audit_log),
        )

    assert _handler_counts() == {
        "root": 2,
        "cinema_showcase": 0,
        "cinema_showcase.payments": 2,
        "cinema_showcase.audit": 2,
    }

    get_logger("tests.duplicates").info("duplicate-probe")
    get_payment_logger("tests.duplicates").info("payment-duplicate-probe")
    get_audit_logger("tests.duplicates").info("audit-duplicate-probe")
    _flush_logging_handlers()

    assert app_log.read_text(encoding="utf-8").count("duplicate-probe") == 1
    assert payments_log.read_text(encoding="utf-8").count("payment-duplicate-probe") == 1
    assert audit_log.read_text(encoding="utf-8").count("audit-duplicate-probe") == 1


def test_text_formatter_uses_stable_utc_timestamp() -> None:
    formatter = RedactingFormatter("%(asctime)s | %(levelname)s | %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="timestamp probe",
        args=(),
        exc_info=None,
    )
    record.created = 0

    assert formatter.format(record) == "1970-01-01T00:00:00.000Z | INFO | timestamp probe"


def test_json_logging_outputs_safe_structured_records(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    configure_logging(
        "INFO",
        log_format="json",
        app_log_file=str(app_log),
        payments_log_file=None,
        audit_log_file=None,
    )

    request_token = set_request_id("json-req-1")
    try:
        get_logger("tests.json").info(
            "JSON event token=%s",
            "json-token-secret",
            extra={"authorization": "Bearer json-auth-secret", "safe_id": "safe-1"},
        )
    finally:
        reset_request_id(request_token)
    _flush_logging_handlers()

    output = app_log.read_text(encoding="utf-8")
    record = json.loads(output.strip())

    assert record["timestamp"].endswith("Z")
    assert record["level"] == "INFO"
    assert record["logger"] == "cinema_showcase.tests.json"
    assert record["request_id"] == "json-req-1"
    assert record["message"] == "JSON event token=<redacted>"
    assert record["metadata"]["authorization"] == REDACTED_VALUE
    assert record["metadata"]["safe_id"] == "safe-1"
    assert "json-token-secret" not in output
    assert "json-auth-secret" not in output


def test_configure_logging_rotates_app_log(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    configure_logging(
        "INFO",
        app_log_file=str(app_log),
        payments_log_file=None,
        audit_log_file=None,
        max_bytes=250,
        backup_count=2,
    )

    logger = get_logger("tests.rotation")
    for index in range(20):
        logger.info("rotation probe %s %s", index, "x" * 80)

    _flush_logging_handlers()

    assert app_log.exists()
    assert (tmp_path / "app.log.1").exists()


def test_request_logging_middleware_binds_and_returns_request_id(tmp_path: Path) -> None:
    app_log = tmp_path / "app.log"
    configure_logging(
        "INFO",
        app_log_file=str(app_log),
        payments_log_file=None,
        audit_log_file=None,
    )

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        get_logger("tests.request").info("Inside request")
        return {"ok": True}

    response = TestClient(app).get("/ping", headers={"X-Correlation-ID": "corr-123"})
    _flush_logging_handlers()

    output = app_log.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "corr-123"
    assert "request_id=corr-123" in output
    assert "Inside request" in output
    assert "HTTP request completed" in output


def _flush_logging_handlers() -> None:
    for logger_name in ("", "cinema_showcase", "cinema_showcase.payments", "cinema_showcase.audit"):
        for handler in logging.getLogger(logger_name).handlers:
            handler.flush()


def _handler_counts() -> dict[str, int]:
    logger_names = ("cinema_showcase", "cinema_showcase.payments", "cinema_showcase.audit")
    return {
        "root": len(logging.getLogger().handlers),
        **{logger_name: len(logging.getLogger(logger_name).handlers) for logger_name in logger_names},
    }
