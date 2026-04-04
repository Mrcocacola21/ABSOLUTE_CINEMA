"""Session and schedule-related schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, field_validator, model_validator

from app.core.constants import (
    ALLOWED_SORT_FIELDS,
    ALLOWED_SORT_ORDERS,
    SessionStatuses,
)
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText
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
    def validate_session_state(self) -> "SessionBase":
        """Ensure session timing and stored counters remain internally consistent."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        if self.available_seats > self.total_seats:
            raise ValueError("available_seats cannot exceed total_seats.")
        return self


class SessionCreate(BaseSchema):
    """Payload for creating a session slot for an existing movie."""

    movie_id: str
    start_time: datetime
    end_time: datetime
    price: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_time_window(self) -> "SessionCreate":
        """Ensure the requested session slot has a positive duration."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        return self


class SessionUpdate(BaseSchema):
    """Payload for updating a session."""

    movie_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_partial_time_window(self) -> "SessionUpdate":
        """Ensure explicitly provided start/end pairs form a valid slot."""
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        return self


class SessionBatchCreate(BaseSchema):
    """Payload for creating the same session slot on multiple calendar dates."""

    movie_id: str
    start_time: datetime
    end_time: datetime
    price: float = Field(ge=0)
    dates: list[date] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_batch_slot(self) -> "SessionBatchCreate":
        """Ensure the template slot is valid and dates are unique."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        if len(set(self.dates)) != len(self.dates):
            raise ValueError("dates must be unique.")
        return self


class SessionRead(SessionBase):
    """Session DTO returned by the API."""

    id: str
    created_at: datetime
    updated_at: datetime | None = None


class SessionDetailsRead(SessionRead):
    """Session DTO enriched with movie information."""

    movie: MovieRead


class SessionBatchRejectedDateRead(BaseSchema):
    """One requested date that could not be created in batch mode."""

    date: date
    start_time: datetime
    end_time: datetime
    code: str
    message: str
    blocking_session_id: str | None = None


class SessionBatchCreateRead(BaseSchema):
    """Result of a batch session creation attempt."""

    requested_dates: list[date]
    requested_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    created_sessions: list[SessionDetailsRead] = Field(default_factory=list)
    rejected_dates: list[SessionBatchRejectedDateRead] = Field(default_factory=list)


class ScheduleItemRead(BaseSchema):
    """Schedule item optimized for list views."""

    id: str
    movie_id: str
    movie_title: LocalizedText
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
