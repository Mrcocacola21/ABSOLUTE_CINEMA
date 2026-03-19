"""Logging configuration helpers based on the standard library."""

from __future__ import annotations

import logging
import logging.config

LOGGER_NAME = "cinema_showcase"


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging using a consistent structured format."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
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
