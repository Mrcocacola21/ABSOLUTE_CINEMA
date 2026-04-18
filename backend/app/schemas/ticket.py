"""Ticket-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.core.constants import TicketStatuses
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText

TICKET_STATUS_VALUES = (TicketStatuses.PURCHASED, TicketStatuses.CANCELLED)


class TicketPurchaseRequest(BaseSchema):
    """Payload for purchasing a ticket."""

    session_id: str
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)


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

    @model_validator(mode="after")
    def validate_ticket_state(self) -> "TicketRead":
        """Keep ticket lifecycle values internally consistent."""
        if self.status not in TICKET_STATUS_VALUES:
            raise ValueError("Unsupported ticket status.")
        if self.status == TicketStatuses.CANCELLED and self.cancelled_at is None:
            raise ValueError("Cancelled tickets must include cancelled_at.")
        if self.status == TicketStatuses.PURCHASED and self.cancelled_at is not None:
            raise ValueError("Purchased tickets cannot include cancelled_at.")
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
