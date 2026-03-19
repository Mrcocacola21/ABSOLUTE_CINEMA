"""Factory for standardized API response envelopes."""

from __future__ import annotations

from typing import TypeVar

from app.core.responses import ApiResponse, ResponseMeta

T = TypeVar("T")


class ApiResponseFactory:
    """Build consistent success responses across the API."""

    @staticmethod
    def success(
        data: T,
        message: str = "Request completed successfully.",
        meta: ResponseMeta | None = None,
    ) -> ApiResponse[T]:
        """Create a standard successful response envelope."""
        return ApiResponse[T](message=message, data=data, meta=meta)

    @staticmethod
    def created(
        data: T,
        message: str = "Resource created successfully.",
        meta: ResponseMeta | None = None,
    ) -> ApiResponse[T]:
        """Create a standard successful response envelope for created resources."""
        return ApiResponseFactory.success(data=data, message=message, meta=meta)
