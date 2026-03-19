"""Ticket-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class TicketPurchaseRequest(BaseSchema):
    """Payload for purchasing a ticket."""

    session_id: str
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)


class TicketRead(BaseSchema):
    """Ticket DTO returned by the API."""

    id: str
    user_id: str
    session_id: str
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)
    price: float = Field(ge=0)
    status: str
    purchased_at: datetime
