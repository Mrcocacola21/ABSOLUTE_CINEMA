"""Seat-related schemas."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import BaseSchema


class SeatAvailabilityRead(BaseSchema):
    """Seat availability DTO used for session maps."""

    row: int = Field(ge=1)
    number: int = Field(ge=1)
    is_available: bool
