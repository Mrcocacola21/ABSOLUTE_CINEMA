"""Query parameter dependencies for pagination and schedule browsing."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import ValidationError

from app.core.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_SORT_BY,
    DEFAULT_SORT_ORDER,
    MAX_PAGE_LIMIT,
)
from app.core.exceptions import ValidationException
from app.schemas.common import PaginationParams
from app.schemas.session import ScheduleQueryParams


def get_pagination_params(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PAGE_LIMIT,
            description="Maximum number of items to return in one response page.",
        ),
    ] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Zero-based number of items to skip before the current page starts.",
        ),
    ] = 0,
) -> PaginationParams:
    """Build pagination parameters from request query arguments."""
    return PaginationParams(limit=limit, offset=offset)


def get_schedule_query_params(
    sort_by: Annotated[
        str,
        Query(description="Schedule sort field. Supported values are `start_time`, `price`, and `available_seats`."),
    ] = DEFAULT_SORT_BY,
    sort_order: Annotated[
        str,
        Query(description="Schedule sort order. Supported values are `asc` and `desc`."),
    ] = DEFAULT_SORT_ORDER,
    movie_id: Annotated[
        str | None,
        Query(description="Optional movie identifier used to return sessions for one movie only."),
    ] = None,
) -> ScheduleQueryParams:
    """Build schedule filter and sorting parameters from the query string."""
    try:
        return ScheduleQueryParams(
            sort_by=sort_by,
            sort_order=sort_order,
            movie_id=movie_id,
        )
    except ValidationError as exc:
        errors = exc.errors()
        first_error = errors[0] if errors else None
        message = str(first_error.get("msg")) if isinstance(first_error, dict) and first_error.get("msg") else None
        if message and message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        raise ValidationException(message or "Invalid schedule query parameters.") from exc
