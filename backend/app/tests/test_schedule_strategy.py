"""Unit tests for schedule sorting strategies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ValidationException
from app.schemas.localization import LocalizedText
from app.strategies.schedule_sorting import ScheduleSortingStrategyFactory


@dataclass(frozen=True)
class ScheduleSortItem:
    movie_title: object
    available_seats: int
    start_time: datetime


def build_items() -> list[ScheduleSortItem]:
    return [
        ScheduleSortItem(
            movie_title=LocalizedText(uk="Beta", en="Alpha"),
            available_seats=40,
            start_time=datetime(2026, 5, 6, 18, 0, tzinfo=timezone.utc),
        ),
        ScheduleSortItem(
            movie_title=LocalizedText(uk="alpha", en="Zulu"),
            available_seats=12,
            start_time=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        ),
        ScheduleSortItem(
            movie_title=LocalizedText(uk="Gamma", en="Beta"),
            available_seats=88,
            start_time=datetime(2026, 5, 6, 15, 0, tzinfo=timezone.utc),
        ),
    ]


def test_sort_by_available_seats_strategy() -> None:
    strategy = ScheduleSortingStrategyFactory.create("available_seats", "desc")

    assert strategy.field_name == "available_seats"
    assert strategy.reverse is True
    assert [item.available_seats for item in strategy.sort(build_items())] == [88, 40, 12]


def test_sort_by_start_time_strategy() -> None:
    strategy = ScheduleSortingStrategyFactory.create("start_time", "asc")

    assert strategy.field_name == "start_time"
    assert strategy.reverse is False
    assert [item.start_time.hour for item in strategy.sort(build_items())] == [12, 15, 18]


def test_sort_by_movie_title_uses_ukrainian_title_case_insensitively() -> None:
    strategy = ScheduleSortingStrategyFactory.create("movie_title", "asc")

    assert strategy.field_name == "movie_title"
    assert [item.movie_title.resolve("uk") for item in strategy.sort(build_items())] == [
        "alpha",
        "Beta",
        "Gamma",
    ]


def test_sort_by_movie_title_descending_supports_plain_legacy_strings() -> None:
    items = [
        ScheduleSortItem("zeta", 1, datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)),
        ScheduleSortItem("Alpha", 1, datetime(2026, 5, 6, 13, 0, tzinfo=timezone.utc)),
        ScheduleSortItem("beta", 1, datetime(2026, 5, 6, 14, 0, tzinfo=timezone.utc)),
    ]
    strategy = ScheduleSortingStrategyFactory.create("movie_title", "desc")

    assert [item.movie_title for item in strategy.sort(items)] == ["zeta", "beta", "Alpha"]


def test_sorting_keeps_stable_order_for_equal_keys() -> None:
    first = ScheduleSortItem("Same", 10, datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc))
    second = ScheduleSortItem("Same", 10, datetime(2026, 5, 6, 13, 0, tzinfo=timezone.utc))
    strategy = ScheduleSortingStrategyFactory.create("available_seats", "asc")

    assert strategy.sort([first, second]) == [first, second]


def test_factory_rejects_unsupported_sort_field() -> None:
    with pytest.raises(ValidationException, match="Unsupported sort field."):
        ScheduleSortingStrategyFactory.create("price", "asc")


def test_factory_rejects_unsupported_sort_order() -> None:
    with pytest.raises(ValidationException, match="Unsupported sort order."):
        ScheduleSortingStrategyFactory.create("start_time", "sideways")
