"""Logging configuration helpers based on the standard library."""

from __future__ import annotations

import contextvars
import copy
import json
import logging
import logging.config
import re
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

LOGGER_NAME = "cinema_showcase"
PAYMENTS_LOGGER_NAME = f"{LOGGER_NAME}.payments"
AUDIT_LOGGER_NAME = f"{LOGGER_NAME}.audit"
REDACTED_VALUE = "<redacted>"
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5
DEFAULT_REQUEST_ID = "-"
DEFAULT_LOG_FORMAT = "text"
LOG_FORMAT_TEXT = "text"
LOG_FORMAT_JSON = "json"

_CONFIGURE_LOGGING_LOCK = threading.RLock()
_REQUEST_ID_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "cinema_showcase_request_id",
    default=DEFAULT_REQUEST_ID,
)
_RESERVED_LOG_RECORD_ATTRS: Final[set[str]] = set(
    logging.LogRecord(
        name="reserved",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
) | {"asctime", "message"}

SENSITIVE_KEY_MARKERS = (
    "password",
    "passphrase",
    "token",
    "secret",
    "authorization",
    "auth_header",
    "auth_headers",
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "jwt",
    "cookie",
    "signature",
    "webhook_signature",
    "x_fake_payment_signature",
    "provider_secret",
    "client_secret",
    "card",
    "pan",
    "cvv",
    "cvc",
)
SENSITIVE_STRING_KEY_PATTERN = (
    r"password",
    r"passphrase",
    r"(?:access[_-]?token|refresh[_-]?token|token)",
    r"(?:jwt[_-]?secret(?:[_-]?key)?|secret(?:[_-]?key)?)",
    r"authorization",
    r"auth[_-]?headers?",
    r"api[_-]?key",
    r"access[_-]?key",
    r"cookie",
    r"(?:webhook[_-]?)?signature",
    r"x[_-]?fake[_-]?payment[_-]?signature",
    r"provider[_-]?secret",
    r"client[_-]?secret",
    r"card(?:[_-]?number)?",
    r"pan",
    r"cvv",
    r"cvc",
)
AUTHORIZATION_HEADER_PATTERN = re.compile(
    r"(?P<prefix>[\"']?authorization[\"']?\s*[:=]\s*)(?P<quote>[\"']?)"
    r"(?:(?:basic|bearer)\s+)?[^\"',}\]\s]+(?P=quote)",
    re.IGNORECASE,
)
BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[^\"',}\]\s]+", re.IGNORECASE)
SENSITIVE_KEY_VALUE_PATTERN = re.compile(
    rf"(?P<prefix>[\"']?(?:{'|'.join(SENSITIVE_STRING_KEY_PATTERN)})[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"']?)(?P<value>(?:basic|bearer)\s+[^\"',}\]\s]+|[^\"',}\]\s]+)(?P=quote)",
    re.IGNORECASE,
)


def _normalize_key_name(key: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower()


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return False

    normalized = _normalize_key_name(key)
    return any(marker in normalized for marker in SENSITIVE_KEY_MARKERS)


def sanitize_for_logging(value: object) -> object:
    """Return a log-safe representation with common secrets redacted."""
    if isinstance(value, Mapping):
        return {
            key: REDACTED_VALUE if _is_sensitive_key(key) else sanitize_for_logging(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(sanitize_for_logging(item) for item in value)
    if isinstance(value, list):
        return [sanitize_for_logging(item) for item in value]
    if isinstance(value, set):
        return {sanitize_for_logging(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(sanitize_for_logging(item) for item in value)
    if isinstance(value, str):
        return _sanitize_log_string(value)
    return value


def _sanitize_log_string(value: str) -> str:
    sanitized = AUTHORIZATION_HEADER_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{match.group('quote')}{REDACTED_VALUE}{match.group('quote')}",
        value,
    )
    sanitized = BEARER_TOKEN_PATTERN.sub(f"Bearer {REDACTED_VALUE}", sanitized)
    sanitized = SENSITIVE_KEY_VALUE_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{match.group('quote')}{REDACTED_VALUE}{match.group('quote')}",
        sanitized,
    )
    return sanitized


def _sanitize_log_args(args: object) -> object:
    if isinstance(args, Mapping):
        return {key: sanitize_for_logging(value) for key, value in args.items()}
    if isinstance(args, tuple):
        return tuple(sanitize_for_logging(arg) for arg in args)
    if isinstance(args, list):
        return tuple(sanitize_for_logging(arg) for arg in args)
    return sanitize_for_logging(args)


def get_request_id() -> str:
    """Return the request/correlation id bound to the current execution context."""
    return _REQUEST_ID_CONTEXT.get()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    """Bind a request/correlation id to the current execution context."""
    normalized = request_id.strip() or DEFAULT_REQUEST_ID
    return _REQUEST_ID_CONTEXT.set(normalized)


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Restore the previous request/correlation id context."""
    _REQUEST_ID_CONTEXT.reset(token)


class RequestContextFilter(logging.Filter):
    """Attach request-scoped context to every log record handled by the app."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


class RedactingFormatter(logging.Formatter):
    """Logging formatter that masks common credential-like values and extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        sanitized_record = self._prepare_record(record)
        if sanitized_record.args:
            sanitized_record.args = _sanitize_log_args(sanitized_record.args)
        else:
            sanitized_record.msg = sanitize_for_logging(sanitized_record.msg)
        sanitized_record.exc_text = None
        output = super().format(sanitized_record)
        extra_fields = self._format_extra_fields(sanitized_record)
        if extra_fields:
            output = f"{output} | {extra_fields}"
        return _sanitize_log_string(output)

    def formatException(self, ei) -> str:  # noqa: N802 - stdlib logging API
        return _sanitize_log_string(super().formatException(ei))

    def formatTime(  # noqa: N802 - stdlib logging API
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        _ = datefmt
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _prepare_record(self, record: logging.LogRecord) -> logging.LogRecord:
        sanitized_record = copy.copy(record)
        if not hasattr(sanitized_record, "request_id"):
            sanitized_record.request_id = get_request_id()
        self._sanitize_record_extras(sanitized_record)
        return sanitized_record

    def _sanitize_record_extras(self, record: logging.LogRecord) -> None:
        for key, value in list(record.__dict__.items()):
            if key in _RESERVED_LOG_RECORD_ATTRS or key == "request_id":
                continue
            setattr(
                record,
                key,
                REDACTED_VALUE if _is_sensitive_key(key) else sanitize_for_logging(value),
            )

    def _format_extra_fields(self, record: logging.LogRecord) -> str:
        fields = []
        for key, safe_value in self._iter_extra_items(record):
            fields.append(f"{key}={self._stringify_extra_value(safe_value)}")
        return " ".join(fields)

    def _iter_extra_items(self, record: logging.LogRecord) -> list[tuple[str, object]]:
        items: list[tuple[str, object]] = []
        for key in sorted(record.__dict__):
            if key in _RESERVED_LOG_RECORD_ATTRS or key == "request_id":
                continue
            value = record.__dict__[key]
            if value is None:
                continue
            safe_value = REDACTED_VALUE if _is_sensitive_key(key) else sanitize_for_logging(value)
            items.append((key, safe_value))
        return items

    def _stringify_extra_value(self, value: object) -> str:
        if isinstance(value, str):
            return _sanitize_log_string(value)
        return _sanitize_log_string(repr(value))


class RedactingJsonFormatter(RedactingFormatter):
    """JSON formatter with the same redaction and request context as text logs."""

    def format(self, record: logging.LogRecord) -> str:
        sanitized_record = self._prepare_record(record)
        if sanitized_record.args:
            sanitized_record.args = _sanitize_log_args(sanitized_record.args)
        else:
            sanitized_record.msg = sanitize_for_logging(sanitized_record.msg)
        sanitized_record.exc_text = None

        payload: dict[str, object] = {
            "timestamp": self.formatTime(sanitized_record),
            "level": sanitized_record.levelname,
            "logger": sanitized_record.name,
            "request_id": sanitized_record.request_id,
            "message": _sanitize_log_string(sanitized_record.getMessage()),
        }
        metadata = dict(self._iter_extra_items(sanitized_record))
        if metadata:
            payload["metadata"] = metadata
        if sanitized_record.exc_info:
            payload["exception"] = self.formatException(sanitized_record.exc_info)
        return _sanitize_log_string(
            json.dumps(payload, ensure_ascii=False, default=_json_default, separators=(",", ":"))
        )


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return str(value)


def _normalize_log_level(level: str | None, *, fallback: str = "INFO") -> str:
    value = (level or fallback).strip().upper()
    return value if value else fallback


def _normalize_log_format(log_format: str | None) -> str:
    value = (log_format or DEFAULT_LOG_FORMAT).strip().lower()
    if value in {LOG_FORMAT_TEXT, LOG_FORMAT_JSON}:
        return value
    return DEFAULT_LOG_FORMAT


def _ensure_log_parent_directory(path: str | None) -> None:
    if not path:
        return
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def configure_logging(
    level: str = "INFO",
    *,
    log_format: str = DEFAULT_LOG_FORMAT,
    file_enabled: bool = True,
    file_level: str | None = None,
    payments_level: str | None = None,
    audit_level: str | None = None,
    app_log_file: str | None = None,
    payments_log_file: str | None = None,
    audit_log_file: str | None = None,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> None:
    """Configure application logging using a consistent redacted format."""
    normalized_level = _normalize_log_level(level)
    normalized_file_level = _normalize_log_level(file_level, fallback=normalized_level)
    normalized_payments_level = _normalize_log_level(payments_level, fallback=normalized_level)
    normalized_audit_level = _normalize_log_level(audit_level, fallback=normalized_level)
    normalized_log_format = _normalize_log_format(log_format)
    formatter_name = "json" if normalized_log_format == LOG_FORMAT_JSON else "standard"

    handlers: dict[str, dict[str, object]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": formatter_name,
            "filters": ["request_context"],
            "level": normalized_level,
        }
    }
    root_handlers = ["console"]
    payments_handlers = ["console"]
    audit_handlers = ["console"]

    if file_enabled:
        for log_file in (app_log_file, payments_log_file, audit_log_file):
            _ensure_log_parent_directory(log_file)

        if app_log_file:
            handlers["app_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": app_log_file,
                "formatter": formatter_name,
                "filters": ["request_context"],
                "level": normalized_file_level,
                "maxBytes": max(1, max_bytes),
                "backupCount": max(0, backup_count),
                "encoding": "utf-8",
            }
            root_handlers.append("app_file")
        if payments_log_file:
            handlers["payments_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": payments_log_file,
                "formatter": formatter_name,
                "filters": ["request_context"],
                "level": normalized_payments_level,
                "maxBytes": max(1, max_bytes),
                "backupCount": max(0, backup_count),
                "encoding": "utf-8",
            }
            payments_handlers.append("payments_file")
        if audit_log_file:
            handlers["audit_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": audit_log_file,
                "formatter": formatter_name,
                "filters": ["request_context"],
                "level": normalized_audit_level,
                "maxBytes": max(1, max_bytes),
                "backupCount": max(0, backup_count),
                "encoding": "utf-8",
            }
            audit_handlers.append("audit_file")

    with _CONFIGURE_LOGGING_LOCK:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "filters": {
                    "request_context": {
                        "()": "app.core.logging.RequestContextFilter",
                    }
                },
                "formatters": {
                    "standard": {
                        "()": "app.core.logging.RedactingFormatter",
                        "format": "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | %(message)s",
                    },
                    "json": {
                        "()": "app.core.logging.RedactingJsonFormatter",
                    },
                },
                "handlers": handlers,
                "loggers": {
                    LOGGER_NAME: {
                        "level": normalized_level,
                        "propagate": True,
                    },
                    PAYMENTS_LOGGER_NAME: {
                        "handlers": payments_handlers,
                        "level": normalized_payments_level,
                        "propagate": False,
                    },
                    AUDIT_LOGGER_NAME: {
                        "handlers": audit_handlers,
                        "level": normalized_audit_level,
                        "propagate": False,
                    },
                },
                "root": {
                    "handlers": root_handlers,
                    "level": normalized_level,
                },
            }
        )


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application logger namespaced under the project logger."""
    logger_name = LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}"
    return logging.getLogger(logger_name)


def get_payment_logger(name: str | None = None) -> logging.Logger:
    """Return a logger for payment/refund/webhook operational events."""
    logger_name = PAYMENTS_LOGGER_NAME if not name else f"{PAYMENTS_LOGGER_NAME}.{name}"
    return logging.getLogger(logger_name)


def get_audit_logger(name: str | None = None) -> logging.Logger:
    """Return a logger for high-value audit/admin events."""
    logger_name = AUDIT_LOGGER_NAME if not name else f"{AUDIT_LOGGER_NAME}.{name}"
    return logging.getLogger(logger_name)
