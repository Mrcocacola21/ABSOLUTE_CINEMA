"""Unit tests for schedule sorting strategies."""

from app.strategies.schedule_sorting import ScheduleSortingStrategyFactory


def test_sort_by_available_seats_strategy() -> None:
    strategy = ScheduleSortingStrategyFactory.create("available_seats", "desc")

    assert strategy.field_name == "available_seats"
    assert strategy.reverse is True


def test_sort_by_start_time_strategy() -> None:
    strategy = ScheduleSortingStrategyFactory.create("start_time", "asc")

    assert strategy.field_name == "start_time"
    assert strategy.reverse is False
