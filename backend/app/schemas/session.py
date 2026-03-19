"""Session and schedule-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.core.constants import (
    ALLOWED_SORT_FIELDS,
    ALLOWED_SORT_ORDERS,
    SessionStatuses,
)
from app.schemas.common import BaseSchema
from app.schemas.movie import MovieRead
from app.schemas.seat import SeatAvailabilityRead


class SessionBase(BaseSchema):
    """Shared session fields."""

    movie_id: str
    start_time: datetime
    end_time: datetime
    price: float = Field(ge=0)
    status: str = SessionStatuses.SCHEDULED
    total_seats: int = Field(ge=0)
    available_seats: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_available_seats(self) -> "SessionBase":
        """Ensure the stored seat counters remain internally consistent."""
        if self.available_seats > self.total_seats:
            raise ValueError("available_seats cannot exceed total_seats.")
        return self


class SessionCreate(BaseSchema):
    """Payload for creating a session slot for an existing movie."""

    movie_id: str
    start_time: datetime
    price: float = Field(ge=0)


class SessionRead(SessionBase):
    """Session DTO returned by the API."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None


class SessionDetailsRead(SessionRead):
    """Session DTO enriched with movie information."""

    movie: MovieRead


class ScheduleItemRead(BaseSchema):
    """Schedule item optimized for list views."""

    id: str
    movie_id: str
    movie_title: str
    poster_url: str | None = None
    age_rating: str | None = None
    genres: list[str] = Field(default_factory=list)
    start_time: datetime
    end_time: datetime
    price: float = Field(ge=0)
    status: str
    available_seats: int = Field(ge=0)
    total_seats: int = Field(ge=0)


class ScheduleQueryParams(BaseSchema):
    """Query parameters supported by the schedule endpoint."""

    sort_by: str = "start_time"
    sort_order: str = "asc"
    movie_id: str | None = None

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str) -> str:
        """Validate supported schedule sort fields."""
        if value not in ALLOWED_SORT_FIELDS:
            raise ValueError("Unsupported sort field.")
        return value

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: str) -> str:
        """Validate supported schedule sort directions."""
        if value not in ALLOWED_SORT_ORDERS:
            raise ValueError("Unsupported sort order.")
        return value


class SessionSeatsRead(BaseSchema):
    """Seat map data for a specific session."""

    session_id: str
    rows_count: int = Field(ge=1)
    seats_per_row: int = Field(ge=1)
    total_seats: int = Field(ge=0)
    available_seats: int = Field(ge=0)
    seats: list[SeatAvailabilityRead]
