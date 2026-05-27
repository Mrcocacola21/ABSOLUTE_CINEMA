"""Request logging middleware."""

from __future__ import annotations

import re
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, reset_request_id, set_request_id

logger = get_logger(__name__)

REQUEST_ID_RESPONSE_HEADER = "X-Request-ID"
REQUEST_ID_HEADER_NAMES = ("x-request-id", "x-correlation-id", "correlation-id")
MAX_REQUEST_ID_LENGTH = 128
REQUEST_ID_SAFE_CHARACTERS = re.compile(r"[^A-Za-z0-9_.:/=-]")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log inbound HTTP requests and their completion status."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log request metadata before and after processing."""
        request_id = self._resolve_request_id(request)
        request_id_token = set_request_id(request_id)
        started_at = time.perf_counter()
        status_code: int | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_RESPONSE_HEADER] = request_id
            return response
        except Exception as exc:
            status_code = 500
            logger.exception(
                "HTTP request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                },
                exc_info=exc,
            )
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "elapsed_ms": round(elapsed_ms, 2),
                },
            )
            reset_request_id(request_id_token)

    def _resolve_request_id(self, request: Request) -> str:
        for header_name in REQUEST_ID_HEADER_NAMES:
            value = request.headers.get(header_name)
            if value and value.strip():
                return self._normalize_request_id(value)
        return uuid4().hex

    def _normalize_request_id(self, value: str) -> str:
        normalized = REQUEST_ID_SAFE_CHARACTERS.sub("-", value.strip())
        normalized = normalized[:MAX_REQUEST_ID_LENGTH].strip("-")
        return normalized or uuid4().hex
