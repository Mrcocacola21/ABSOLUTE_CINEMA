"""Request logging middleware."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log inbound HTTP requests and their completion status."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log request metadata before and after processing."""
        started_at = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "%s %s -> %s (%.2f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
