"""Custom exception hierarchy and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.core.logging import get_logger
from app.core.responses import ErrorResponse

logger = get_logger(__name__)

REQUEST_VALIDATION_PREFIXES = (
    "Value error, ",
    "Assertion failed, ",
)


class AppException(Exception):
    """Base class for controlled application exceptions."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "application_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class AuthenticationException(AppException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_error",
        )


class AuthorizationException(AppException):
    """Raised when a user lacks permissions for an action."""

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="authorization_error",
        )


class NotFoundException(AppException):
    """Raised when a resource cannot be found."""

    def __init__(self, message: str = "Requested resource was not found.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
        )


class ConflictException(AppException):
    """Raised when the requested operation conflicts with current state."""

    def __init__(self, message: str = "Resource conflict detected.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
        )


class ValidationException(AppException):
    """Raised when a business validation rule is violated."""

    def __init__(self, message: str = "Validation failed.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
        )


class DatabaseException(AppException):
    """Raised when an infrastructure database error occurs."""

    def __init__(self, message: str = "Database operation failed.") -> None:
        super().__init__(
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="database_error",
        )


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    """Convert controlled application exceptions into standardized JSON responses."""
    response = ErrorResponse.from_exception(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
    )


async def request_validation_exception_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Convert FastAPI validation errors into the shared error envelope."""
    details = jsonable_encoder(exc.errors())
    response = ErrorResponse.validation_error(
        details,
        message=_extract_request_validation_message(details),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=response.model_dump(mode="json"),
    )


async def unexpected_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions while preserving a stable error contract."""
    logger.exception("Unhandled application exception", exc_info=exc)
    response = ErrorResponse.server_error()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(mode="json"),
    )


async def pymongo_exception_handler(_: Request, exc: PyMongoError) -> JSONResponse:
    """Convert raw MongoDB driver errors into the shared infrastructure error envelope."""
    logger.exception("Unhandled MongoDB exception", exc_info=exc)
    response = ErrorResponse.from_exception(DatabaseException())
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=response.model_dump(mode="json"),
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application."""
    application.add_exception_handler(AppException, app_exception_handler)
    application.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    application.add_exception_handler(PyMongoError, pymongo_exception_handler)
    application.add_exception_handler(Exception, unexpected_exception_handler)


def _extract_request_validation_message(details: list[dict[str, Any]]) -> str:
    """Return the first human-readable request validation message when available."""
    if not details:
        return "Request validation failed."

    raw_message = str(details[0].get("msg", "")).strip()
    if not raw_message:
        return "Request validation failed."

    for prefix in REQUEST_VALIDATION_PREFIXES:
        if raw_message.startswith(prefix):
            raw_message = raw_message[len(prefix) :].strip()
            break

    return raw_message or "Request validation failed."
