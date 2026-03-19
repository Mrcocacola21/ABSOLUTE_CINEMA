"""Unit tests for pagination helpers."""

from app.schemas.common import PaginationParams
from app.utils.pagination import build_pagination_meta


def test_build_pagination_meta_calculates_pages() -> None:
    pagination = PaginationParams(limit=10, offset=20)

    meta = build_pagination_meta(pagination, total=95)

    assert meta.current_page == 3
    assert meta.total_pages == 10
    assert meta.total == 95
