"""Logging configuration helpers based on the standard library."""

from __future__ import annotations

import copy
import logging
import logging.config
import re
from collections.abc import Mapping

LOGGER_NAME = "cinema_showcase"
REDACTED_VALUE = "<redacted>"

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
)
AUTHORIZATION_HEADER_PATTERN = re.compile(
    r"(?P<prefix>[\"']?authorization[\"']?\s*[:=]\s*)(?P<quote>[\"']?)"
    r"(?P<scheme>basic|bearer)\s+[^\"',}\]\s]+(?P=quote)",
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
        lambda match: f"{match.group('prefix')}{match.group('quote')}{match.group('scheme')} {REDACTED_VALUE}{match.group('quote')}",
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


class RedactingFormatter(logging.Formatter):
    """Logging formatter that masks common credential-like values."""

    def format(self, record: logging.LogRecord) -> str:
        sanitized_record = copy.copy(record)
        if sanitized_record.args:
            sanitized_record.args = _sanitize_log_args(sanitized_record.args)
        else:
            sanitized_record.msg = sanitize_for_logging(sanitized_record.msg)
        sanitized_record.exc_text = None
        return _sanitize_log_string(super().format(sanitized_record))

    def formatException(self, ei) -> str:  # noqa: N802 - stdlib logging API
        return _sanitize_log_string(super().formatException(ei))


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging using a consistent structured format."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "()": "app.core.logging.RedactingFormatter",
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": level.upper(),
                }
            },
            "loggers": {
                LOGGER_NAME: {
                    "handlers": ["console"],
                    "level": level.upper(),
                    "propagate": False,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level.upper(),
            },
        }
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application logger namespaced under the project logger."""
    logger_name = LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}"
    return logging.getLogger(logger_name)
