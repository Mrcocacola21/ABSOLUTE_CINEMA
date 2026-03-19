"""Standardized success and error response schemas."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.schemas.common import PaginationMeta

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Metadata container shared by successful API responses."""

    request_id: str | None = None
    pagination: PaginationMeta | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Generic envelope used for successful API responses."""

    success: bool = True
    message: str
    data: T
    meta: ResponseMeta | None = None


class ErrorBody(BaseModel):
    """Payload describing an API error."""

    code: str
    message: str
    details: dict[str, Any] | list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """Envelope used for all API error responses."""

    success: bool = False
    error: ErrorBody

    @classmethod
    def from_exception(cls, exc: Any) -> "ErrorResponse":
        """Build an error response from a controlled application exception."""
        return cls(
            error=ErrorBody(
                code=getattr(exc, "code", "application_error"),
                message=getattr(exc, "message", str(exc)),
                details=getattr(exc, "details", None),
            )
        )

    @classmethod
    def validation_error(cls, details: list[dict[str, Any]]) -> "ErrorResponse":
        """Build an error response for request validation failures."""
        return cls(
            error=ErrorBody(
                code="request_validation_error",
                message="Request validation failed.",
                details=details,
            )
        )

    @classmethod
    def server_error(cls) -> "ErrorResponse":
        """Build an error response for unexpected server-side failures."""
        return cls(
            error=ErrorBody(
                code="internal_server_error",
                message="An unexpected server error occurred.",
            )
        )
