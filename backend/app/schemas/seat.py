"""Seat-related schemas."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import BaseSchema


class SeatAvailabilityRead(BaseSchema):
    """Seat availability DTO used for session maps."""

    row: int = Field(ge=1, description="One-based row number.")
    number: int = Field(ge=1, description="One-based seat number within the row.")
    is_available: bool = Field(description="Whether this seat can currently be purchased.")
