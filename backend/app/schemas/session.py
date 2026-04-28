"""Session and schedule-related schemas."""

from __future__ import annotations

from datetime import date as calendar_date, datetime
from typing import Final

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    ALLOWED_SORT_FIELDS,
    ALLOWED_SORT_ORDERS,
    SessionStatuses,
)
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText
from app.schemas.movie import MovieRead
from app.schemas.seat import SeatAvailabilityRead

SESSION_STATUS_VALUES: Final[tuple[str, ...]] = (
    SessionStatuses.SCHEDULED,
    SessionStatuses.CANCELLED,
    SessionStatuses.COMPLETED,
)
SESSION_PRICE_MAX: Final[float] = 1000.0


def _validate_session_price(value: float | None) -> float | None:
    if value is None:
        return None
    if round(value, 2) != value:
        raise ValueError("price must have at most two decimal places.")
    return value


class SessionBase(BaseSchema):
    """Shared session fields."""

    movie_id: str = Field(description="Identifier of the movie shown in this session.")
    start_time: datetime = Field(description="Session start time in ISO 8601 format.")
    end_time: datetime = Field(description="Session end time in ISO 8601 format.")
    price: float = Field(gt=0, le=SESSION_PRICE_MAX, description="Ticket price for the session.")
    status: str = Field(
        default=SessionStatuses.SCHEDULED,
        description="Session lifecycle status.",
        json_schema_extra={"enum": list(SESSION_STATUS_VALUES)},
    )
    total_seats: int = Field(ge=1, description="Total seat count available in the hall for this session.")
    available_seats: int = Field(ge=0, description="Remaining available seats for this session.")

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        """Keep session prices positive and currency-shaped."""
        return _validate_session_price(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Restrict stored session statuses to the supported lifecycle values."""
        if value not in SESSION_STATUS_VALUES:
            raise ValueError("Unsupported session status.")
        return value

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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    movie_id: str = Field(description="Identifier of the movie being scheduled.")
    start_time: datetime = Field(description="Requested session start time in ISO 8601 format.")
    end_time: datetime = Field(description="Requested session end time in ISO 8601 format.")
    price: float = Field(gt=0, le=SESSION_PRICE_MAX, description="Requested ticket price for the session.")

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        """Reject zero or overly precise prices before business validation runs."""
        return _validate_session_price(value)

    @model_validator(mode="after")
    def validate_time_window(self) -> "SessionCreate":
        """Ensure the requested session slot has a positive duration."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        return self


class SessionUpdate(BaseSchema):
    """Payload for updating a session."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    movie_id: str | None = Field(default=None, description="Optional new movie identifier.")
    start_time: datetime | None = Field(default=None, description="Optional new start time.")
    end_time: datetime | None = Field(default=None, description="Optional new end time.")
    price: float | None = Field(
        default=None,
        gt=0,
        le=SESSION_PRICE_MAX,
        description="Optional new ticket price.",
    )

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float | None) -> float | None:
        """Apply the same currency formatting rules to partial updates."""
        return _validate_session_price(value)

    @model_validator(mode="after")
    def validate_partial_time_window(self) -> "SessionUpdate":
        """Ensure explicitly provided start/end pairs form a valid slot."""
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time.")
        return self


class SessionBatchCreate(BaseSchema):
    """Payload for creating the same session slot on multiple calendar dates."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    movie_id: str = Field(description="Identifier of the movie being scheduled.")
    start_time: datetime = Field(description="Template start time applied to each requested date.")
    end_time: datetime = Field(description="Template end time applied to each requested date.")
    price: float = Field(gt=0, le=SESSION_PRICE_MAX, description="Ticket price used for each created session.")
    dates: list[calendar_date] = Field(
        min_length=1,
        description="Calendar dates on which to create the requested slot.",
    )

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        """Keep batch-created session prices aligned with single-session rules."""
        return _validate_session_price(value)

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

    id: str = Field(description="Session identifier.")
    created_at: datetime = Field(description="Session creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Last session update timestamp, if any.")


class SessionDetailsRead(SessionRead):
    """Session DTO enriched with movie information."""

    movie: MovieRead = Field(description="Nested movie payload for the session.")


class SessionBatchRejectedDateRead(BaseSchema):
    """One requested date that could not be created in batch mode."""

    date: calendar_date = Field(description="Requested date that could not be scheduled.")
    start_time: datetime = Field(description="Resolved start time for the rejected date.")
    end_time: datetime = Field(description="Resolved end time for the rejected date.")
    code: str = Field(description="Machine-readable rejection code.")
    message: str = Field(description="Human-readable reason the date was rejected.")
    blocking_session_id: str | None = Field(default=None, description="Conflicting session identifier, when applicable.")


class SessionBatchCreateRead(BaseSchema):
    """Result of a batch session creation attempt."""

    requested_dates: list[calendar_date] = Field(description="All dates included in the batch request.")
    requested_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    created_sessions: list[SessionDetailsRead] = Field(default_factory=list, description="Sessions created successfully.")
    rejected_dates: list[SessionBatchRejectedDateRead] = Field(
        default_factory=list,
        description="Requested dates rejected during batch processing.",
    )


class ScheduleItemRead(BaseSchema):
    """Schedule item optimized for list views."""

    id: str = Field(description="Session identifier.")
    movie_id: str = Field(description="Identifier of the related movie.")
    movie_title: LocalizedText = Field(description="Localized movie title shown in schedule cards and lists.")
    poster_url: str | None = Field(default=None, description="Poster URL or asset path for the related movie.")
    age_rating: str | None = Field(default=None, description="Optional movie age-rating label.")
    genres: list[str] = Field(default_factory=list, description="Normalized genre codes for the related movie.")
    start_time: datetime = Field(description="Session start time.")
    end_time: datetime = Field(description="Session end time.")
    price: float = Field(gt=0, le=SESSION_PRICE_MAX, description="Ticket price for this session.")
    status: str = Field(
        description="Session lifecycle status.",
        json_schema_extra={"enum": list(SESSION_STATUS_VALUES)},
    )
    available_seats: int = Field(ge=0, description="Remaining available seats for this session.")
    total_seats: int = Field(ge=1, description="Total seats available in the hall.")

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: float) -> float:
        """Keep derived schedule items aligned with stored currency precision."""
        return _validate_session_price(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        """Restrict public schedule items to known session statuses."""
        return SessionBase.validate_status(value)


class ScheduleQueryParams(BaseSchema):
    """Query parameters supported by the schedule endpoint."""

    sort_by: str = Field(
        default="start_time",
        description="Schedule sort field.",
        json_schema_extra={"enum": list(ALLOWED_SORT_FIELDS)},
    )
    sort_order: str = Field(
        default="asc",
        description="Schedule sort direction.",
        json_schema_extra={"enum": list(ALLOWED_SORT_ORDERS)},
    )
    movie_id: str | None = Field(default=None, description="Optional movie identifier filter.")

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

    session_id: str = Field(description="Session identifier.")
    rows_count: int = Field(ge=1, description="Number of seat rows in the hall.")
    seats_per_row: int = Field(ge=1, description="Number of seats in each row.")
    total_seats: int = Field(ge=1, description="Total seat count in the hall.")
    available_seats: int = Field(ge=0, description="Remaining available seats.")
    seats: list[SeatAvailabilityRead] = Field(description="Flat list describing availability for every seat in the hall.")
