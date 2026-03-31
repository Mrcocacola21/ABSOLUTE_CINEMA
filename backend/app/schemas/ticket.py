"""Ticket-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


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
    price: float = Field(ge=0)
    status: str
    purchased_at: datetime
    updated_at: datetime | None = None
    cancelled_at: datetime | None = None


class TicketListRead(TicketRead):
    """Ticket DTO enriched with session and optional user details."""

    movie_id: str
    movie_title: str
    session_start_time: datetime
    session_end_time: datetime
    session_status: str
    is_cancellable: bool
    user_name: str | None = None
    user_email: EmailStr | None = None
