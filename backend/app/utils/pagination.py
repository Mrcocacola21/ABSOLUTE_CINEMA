"""Pagination helpers."""

from math import ceil

from app.schemas.common import PaginationMeta, PaginationParams


def build_pagination_meta(pagination: PaginationParams, total: int) -> PaginationMeta:
    """Build pagination metadata for list responses."""
    total_pages = ceil(total / pagination.limit) if pagination.limit else 0
    current_page = (pagination.offset // pagination.limit) + 1 if pagination.limit else 1
    return PaginationMeta(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        current_page=current_page,
        total_pages=total_pages,
    )
