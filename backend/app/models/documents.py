"""Typed document models representing raw MongoDB payloads."""

from __future__ import annotations

from datetime import datetime
from typing import NotRequired, TypedDict


class UserDocument(TypedDict):
    """Raw MongoDB user document."""

    name: str
    email: str
    password_hash: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class MovieDocument(TypedDict):
    """Raw MongoDB movie document."""

    title: str
    description: str
    duration_minutes: int
    poster_url: NotRequired[str | None]
    age_rating: NotRequired[str | None]
    genres: list[str]
    is_active: bool
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class SessionDocument(TypedDict):
    """Raw MongoDB session document."""

    movie_id: str
    start_time: datetime
    end_time: datetime
    price: float
    status: str
    total_seats: int
    available_seats: int
    created_at: datetime
    updated_at: NotRequired[datetime | None]


class TicketDocument(TypedDict):
    """Raw MongoDB ticket document."""

    user_id: str
    session_id: str
    seat_row: int
    seat_number: int
    price: float
    status: str
    purchased_at: datetime
