"""Query parameter dependencies for pagination and schedule browsing."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from app.core.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_SORT_BY,
    DEFAULT_SORT_ORDER,
    MAX_PAGE_LIMIT,
)
from app.schemas.common import PaginationParams
from app.schemas.session import ScheduleQueryParams


def get_pagination_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginationParams:
    """Build pagination parameters from request query arguments."""
    return PaginationParams(limit=limit, offset=offset)


def get_schedule_query_params(
    sort_by: Annotated[str, Query()] = DEFAULT_SORT_BY,
    sort_order: Annotated[str, Query()] = DEFAULT_SORT_ORDER,
    movie_id: Annotated[str | None, Query()] = None,
) -> ScheduleQueryParams:
    """Build schedule filter and sorting parameters from the query string."""
    return ScheduleQueryParams(
        sort_by=sort_by,
        sort_order=sort_order,
        movie_id=movie_id,
    )
