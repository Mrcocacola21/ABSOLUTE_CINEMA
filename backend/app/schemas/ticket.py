"""Ticket-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, model_validator

from app.core.constants import TicketStatuses
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText

TICKET_STATUS_VALUES = (TicketStatuses.PURCHASED, TicketStatuses.CANCELLED)


class TicketPurchaseRequest(BaseSchema):
    """Payload for purchasing a ticket."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "session_id": "6803a522e5d4c4d94e7e1a10",
                "seat_row": 3,
                "seat_number": 8,
            }
        },
    )

    session_id: str = Field(description="Identifier of the scheduled session being purchased.")
    seat_row: int = Field(
        ge=1,
        description="One-based seat row inside the configured one-hall layout.",
    )
    seat_number: int = Field(
        ge=1,
        description="One-based seat number inside the selected row.",
    )


class TicketRead(BaseSchema):
    """Ticket DTO returned by the API."""

    id: str
    order_id: str | None = None
    user_id: str
    session_id: str
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)
    price: float = Field(gt=0)
    status: str
    purchased_at: datetime
    updated_at: datetime | None = None
    cancelled_at: datetime | None = None
    checked_in_at: datetime | None = None

    @model_validator(mode="after")
    def validate_ticket_state(self) -> "TicketRead":
        """Keep ticket lifecycle values internally consistent."""
        if self.status not in TICKET_STATUS_VALUES:
            raise ValueError("Unsupported ticket status.")
        if self.status == TicketStatuses.CANCELLED and self.cancelled_at is None:
            raise ValueError("Cancelled tickets must include cancelled_at.")
        if self.status == TicketStatuses.PURCHASED and self.cancelled_at is not None:
            raise ValueError("Purchased tickets cannot include cancelled_at.")
        if self.status == TicketStatuses.CANCELLED and self.checked_in_at is not None:
            raise ValueError("Cancelled tickets cannot be checked in.")
        return self


class TicketListRead(TicketRead):
    """Ticket DTO enriched with session and optional user details."""

    movie_id: str
    movie_title: LocalizedText
    session_start_time: datetime
    session_end_time: datetime
    session_status: str
    is_cancellable: bool
    user_name: str | None = None
    user_email: EmailStr | None = None
    order_status: str | None = None
    order_created_at: datetime | None = None
    order_total_price: float | None = None
    order_tickets_count: int | None = None
    order_validation_token: str | None = None
