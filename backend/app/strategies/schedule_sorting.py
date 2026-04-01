"""Sorting strategies for schedule browsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from app.core.constants import ALLOWED_SORT_FIELDS, ALLOWED_SORT_ORDERS
from app.core.exceptions import ValidationException
from app.schemas.localization import LocalizedText

SortableItem = TypeVar("SortableItem")


class ScheduleSortingStrategy(ABC):
    """Base strategy describing how schedule items should be sorted."""

    def __init__(self, sort_order: str) -> None:
        if sort_order not in ALLOWED_SORT_ORDERS:
            raise ValidationException("Unsupported sort order.")
        self.sort_order = sort_order

    @property
    def reverse(self) -> bool:
        """Return whether the items should be sorted descending."""
        return self.sort_order == "desc"

    @property
    @abstractmethod
    def field_name(self) -> str:
        """Return the DTO field to use for sorting."""

    def sort(self, items: list[SortableItem]) -> list[SortableItem]:
        """Return a sorted copy of the given schedule items."""
        return sorted(
            items,
            key=lambda item: getattr(item, self.field_name),
            reverse=self.reverse,
        )


class SortByMovieTitleStrategy(ScheduleSortingStrategy):
    """Sort schedule entries by movie title."""

    @property
    def field_name(self) -> str:
        """Return the movie title field name."""
        return "movie_title"

    def sort(self, items: list[SortableItem]) -> list[SortableItem]:
        """Return a sorted copy of schedule items by their canonical Ukrainian title."""
        return sorted(
            items,
            key=lambda item: self._title_sort_key(getattr(item, self.field_name)),
            reverse=self.reverse,
        )

    @staticmethod
    def _title_sort_key(value: object) -> str:
        if isinstance(value, LocalizedText):
            return value.resolve("uk").casefold()
        return str(value).casefold()


class SortByAvailableSeatsStrategy(ScheduleSortingStrategy):
    """Sort schedule entries by available seat count."""

    @property
    def field_name(self) -> str:
        """Return the field storing the available seats count."""
        return "available_seats"


class SortByStartTimeStrategy(ScheduleSortingStrategy):
    """Sort schedule entries by session start timestamp."""

    @property
    def field_name(self) -> str:
        """Return the field storing the session start timestamp."""
        return "start_time"


class ScheduleSortingStrategyFactory:
    """Factory resolving the correct schedule sorting strategy."""

    @staticmethod
    def create(sort_by: str, sort_order: str) -> ScheduleSortingStrategy:
        """Return a sorting strategy for the requested schedule field."""
        if sort_by not in ALLOWED_SORT_FIELDS:
            raise ValidationException("Unsupported sort field.")
        if sort_by == "movie_title":
            return SortByMovieTitleStrategy(sort_order)
        if sort_by == "available_seats":
            return SortByAvailableSeatsStrategy(sort_order)
        return SortByStartTimeStrategy(sort_order)
